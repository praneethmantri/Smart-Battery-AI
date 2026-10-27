import logging
import platform
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, Tuple, List
import ctypes
from ctypes import Structure, c_uint, sizeof, byref

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.session import SessionLocal
from app.models.user import User
from app.models.charging_session import ChargingSession
from app.models.telemetry_sample import TelemetrySample
from app.services.device_battery_service import device_battery_service

logger = logging.getLogger(__name__)


# Win32 LastInputInfo structure for measuring user inactivity duration
class LASTINPUTINFO(Structure):
    _fields_ = [
        ("cbSize", c_uint),
        ("dwTime", c_uint),
    ]


class WindowsTelemetryService:
    """
    Privacy-conscious local background telemetry service for Windows laptops.
    Continuously monitors physical battery state and aggregate user active/idle durations,
    automatically detects charging transitions (plug/unplug), and creates REAL charging
    sessions to train personalized ML models over time.
    """

    def __init__(
        self,
        target_user_id: int = 1,
        poll_interval_seconds: int = 120,
        idle_threshold_seconds: float = 60.0,
        max_stored_samples: int = 500,
    ):
        self.target_user_id = target_user_id
        self.poll_interval_seconds = poll_interval_seconds
        self.idle_threshold_seconds = idle_threshold_seconds
        self.max_stored_samples = max_stored_samples

        # Internal state machine
        self.last_plugged_state: Optional[bool] = None
        self.last_poll_time: Optional[datetime] = None
        self.last_battery_percent: Optional[float] = None
        self.active_session_id: Optional[int] = None
        self.session_start_time: Optional[datetime] = None
        self.session_active_seconds: float = 0.0
        self.session_idle_seconds: float = 0.0

        # Daily usage trackers (in-memory accumulators)
        self.today_active_seconds: float = 0.0
        self.today_idle_seconds: float = 0.0
        self.current_day_date = datetime.now(timezone.utc).date()
        self.sleep_events_count: int = 0
        self.collector_running: bool = False

    def get_system_idle_seconds(self) -> float:
        """
        Queries Windows kernel tick count since last user interaction (mouse/keyboard).
        PRIVACY GUARANTEE: Does not inspect keystrokes, applications, titles, or screen content.
        Returns 0.0 on non-Windows platforms or if API query fails.
        """
        if platform.system().upper() != "WINDOWS":
            return 0.0

        try:
            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32
            lii = LASTINPUTINFO()
            lii.cbSize = sizeof(LASTINPUTINFO)
            if user32.GetLastInputInfo(byref(lii)):
                # GetTickCount / GetTickCount64 returns milliseconds since system boot
                if hasattr(kernel32, "GetTickCount64"):
                    millis_now = kernel32.GetTickCount64()
                else:
                    millis_now = kernel32.GetTickCount()
                elapsed_ms = millis_now - lii.dwTime
                return max(0.0, float(elapsed_ms) / 1000.0)
        except Exception as exc:
            logger.debug("Win32 GetLastInputInfo check note: %s", str(exc))

        return 0.0

    def calculate_previous_day_usage(self, db: Session, user_id: int) -> float:
        """
        Computes aggregate active usage minutes recorded during the previous calendar day.
        Falls back to 0.0 if no prior records exist.
        """
        now = datetime.now(timezone.utc)
        yesterday_start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc) - timedelta(days=1)
        yesterday_end = yesterday_start + timedelta(days=1)

        try:
            # Query sum of active screen usage from sessions on yesterday
            total_minutes = (
                db.query(func.sum(ChargingSession.screen_usage_minutes))
                .filter(
                    ChargingSession.user_id == user_id,
                    ChargingSession.start_time >= yesterday_start,
                    ChargingSession.start_time < yesterday_end,
                )
                .scalar()
            )
            if total_minutes is not None and total_minutes > 0:
                return round(float(total_minutes), 1)
        except Exception as exc:
            logger.debug("Previous day usage query fallback: %s", str(exc))

        return 0.0

    def recover_or_sync_active_session(self, db: Session, current_plugged: Optional[bool], current_soc: float) -> None:
        """
        RESTART RECOVERY & DUPLICATE PREVENTION:
        Checks database for any open REAL_WINDOWS session (end_time IS NULL).
        - If laptop is still plugged in: recovers session ID and start time.
        - If laptop is now unplugged: closes the previously open session cleanly.
        """
        open_session = (
            db.query(ChargingSession)
            .filter(
                ChargingSession.user_id == self.target_user_id,
                ChargingSession.end_time.is_(None),
                ChargingSession.data_source == "REAL_WINDOWS",
            )
            .order_by(ChargingSession.start_time.desc())
            .first()
        )

        if open_session:
            if current_plugged is True:
                # Laptop is still plugged in: recover in-memory session reference
                self.active_session_id = open_session.id
                self.session_start_time = open_session.start_time
                logger.info(
                    "Restart recovery: reconnected to active REAL_WINDOWS session #%d (started %s)",
                    open_session.id, open_session.start_time
                )
            elif current_plugged is False:
                # Laptop was unplugged while collector was down: close open session
                now = datetime.now(timezone.utc)
                st = open_session.start_time
                if st.tzinfo is None:
                    st = st.replace(tzinfo=timezone.utc)
                dur = max(0.0, (now - st).total_seconds() / 60.0)
                open_session.end_time = now
                open_session.end_battery_percent = current_soc
                open_session.charging_duration_minutes = round(dur, 1)
                db.commit()
                logger.info(
                    "Restart recovery: closed uncompleted session #%d after offline unplug",
                    open_session.id
                )
                self.active_session_id = None
                self.session_start_time = None

    def poll_once(self, db: Optional[Session] = None) -> Dict[str, Any]:
        """
        Executes a single telemetry polling cycle:
        1. Queries physical battery sensors via psutil.
        2. Queries user idle time via Win32 API.
        3. Detects sleep/wake gaps.
        4. Detects charging transitions (unplugged -> plugged, plugged -> unplugged).
        5. Persists real sessions and rate-limited telemetry samples.
        """
        now = datetime.now(timezone.utc)
        should_close_session = False
        if db is None:
            db = SessionLocal()
            should_close_session = True

        transition_event = None
        sample_record = None

        try:
            # 1. Query hardware battery status
            batt_info = device_battery_service.get_battery_status()
            current_soc = batt_info.get("battery_percent")
            current_plugged = batt_info.get("is_plugged_in")
            secs_left = batt_info.get("seconds_left")
            source_tag = batt_info.get("source", "REAL_WINDOWS")

            # Fallback if hardware battery is completely unavailable
            if current_soc is None:
                current_soc = self.last_battery_percent or 50.0
            if current_plugged is None:
                current_plugged = self.last_plugged_state if self.last_plugged_state is not None else False

            # 2. Query user activity (idle seconds)
            idle_seconds = self.get_system_idle_seconds()
            is_user_active = idle_seconds < self.idle_threshold_seconds

            # 3. Detect sleep / wake gaps
            sleep_gap_seconds = 0.0
            if self.last_poll_time is not None:
                wall_elapsed = (now - self.last_poll_time).total_seconds()
                # If gap is significantly larger than 2x poll interval, system was asleep
                expected_max = self.poll_interval_seconds * 2.2
                if wall_elapsed > expected_max:
                    sleep_gap_seconds = max(0.0, wall_elapsed - self.poll_interval_seconds)
                    self.sleep_events_count += 1
                    logger.info("Detected sleep/suspend period: %.1f seconds", sleep_gap_seconds)
                else:
                    # Accumulate activity durations
                    if is_user_active:
                        self.today_active_seconds += wall_elapsed
                        if current_plugged:
                            self.session_active_seconds += wall_elapsed
                    else:
                        self.today_idle_seconds += wall_elapsed
                        if current_plugged:
                            self.session_idle_seconds += wall_elapsed

            # Reset daily counters on date change
            if now.date() != self.current_day_date:
                self.current_day_date = now.date()
                self.today_active_seconds = 0.0
                self.today_idle_seconds = 0.0

            # 4. First poll: sync active session with DB to handle restart recovery
            if self.last_plugged_state is None:
                self.recover_or_sync_active_session(db, current_plugged, current_soc)

            # 5. Charging Transition Detection State Machine
            # -------------------------------------------------------------
            # Case A: UNPLUGGED -> PLUGGED (Start Charging Session)
            # -------------------------------------------------------------
            if (self.last_plugged_state is False or self.last_plugged_state is None) and current_plugged is True:
                if self.active_session_id is None:
                    # Ensure user exists in DB before creating session
                    user = db.query(User).filter(User.id == self.target_user_id).first()
                    if not user:
                        user = User(id=self.target_user_id, name="Local Laptop User", email="laptop.telemetry@local")
                        db.add(user)
                        db.commit()

                    prev_usage = self.calculate_previous_day_usage(db, self.target_user_id)
                    new_session = ChargingSession(
                        user_id=self.target_user_id,
                        start_time=now,
                        end_time=None,
                        start_battery_percent=current_soc,
                        end_battery_percent=None,
                        charger_type="standard_ac",
                        day_of_week=now.weekday(),
                        data_source="REAL_WINDOWS",
                        screen_usage_minutes=0.0,
                        idle_usage_minutes=0.0,
                        previous_day_usage_minutes=prev_usage,
                    )
                    db.add(new_session)
                    db.commit()
                    db.refresh(new_session)

                    self.active_session_id = new_session.id
                    self.session_start_time = now
                    self.session_active_seconds = 0.0
                    self.session_idle_seconds = 0.0
                    transition_event = "PLUG_DETECTED_SESSION_STARTED"
                    logger.info("Transition: Plug detected! Started REAL_WINDOWS session #%d at %.1f%%", new_session.id, current_soc)

            # -------------------------------------------------------------
            # Case B: PLUGGED -> UNPLUGGED (Finish Charging Session)
            # -------------------------------------------------------------
            elif self.last_plugged_state is True and current_plugged is False:
                if self.active_session_id is not None:
                    sess = db.query(ChargingSession).filter(ChargingSession.id == self.active_session_id).first()
                    if sess:
                        st = sess.start_time
                        if st.tzinfo is None:
                            st = st.replace(tzinfo=timezone.utc)
                        duration = max(0.0, (now - st).total_seconds() / 60.0)

                        sess.end_time = now
                        sess.end_battery_percent = current_soc
                        sess.charging_duration_minutes = round(duration, 1)
                        sess.screen_usage_minutes = round(self.session_active_seconds / 60.0, 1)
                        sess.idle_usage_minutes = round(self.session_idle_seconds / 60.0, 1)
                        db.commit()
                        logger.info(
                            "Transition: Unplug detected! Completed session #%d (duration=%.1f min, start=%.1f%%, end=%.1f%%)",
                            sess.id, duration, sess.start_battery_percent, current_soc
                        )
                        transition_event = "UNPLUG_DETECTED_SESSION_COMPLETED"

                    self.active_session_id = None
                    self.session_start_time = None
                    self.session_active_seconds = 0.0
                    self.session_idle_seconds = 0.0

            # -------------------------------------------------------------
            # Case C: PLUGGED -> PLUGGED (Duplicate Prevention & Periodic Checkpoint)
            # -------------------------------------------------------------
            elif self.last_plugged_state is True and current_plugged is True:
                # Update partial progress on open session
                if self.active_session_id is not None:
                    sess = db.query(ChargingSession).filter(ChargingSession.id == self.active_session_id).first()
                    if sess:
                        sess.end_battery_percent = current_soc
                        sess.screen_usage_minutes = round(self.session_active_seconds / 60.0, 1)
                        sess.idle_usage_minutes = round(self.session_idle_seconds / 60.0, 1)
                        db.commit()

            # 6. Record rate-limited telemetry sample with rapid duplicate-write suppression
            # Ensure user exists before inserting sample
            user = db.query(User).filter(User.id == self.target_user_id).first()
            if not user:
                user = User(id=self.target_user_id, name="Local Laptop User", email="laptop.telemetry@local")
                db.add(user)
                db.commit()

            # Duplicate-write suppression:
            # If a sample was recorded less than 15s ago with unchanged battery and power state,
            # suppress redundant writes (e.g. rapid /poll-now clicks or immediate CLI execution).
            latest_sample = (
                db.query(TelemetrySample)
                .filter(TelemetrySample.user_id == self.target_user_id)
                .order_by(TelemetrySample.timestamp.desc())
                .first()
            )
            should_insert_sample = True
            if latest_sample and transition_event is None:
                l_ts = latest_sample.timestamp
                if l_ts.tzinfo is None:
                    l_ts = l_ts.replace(tzinfo=timezone.utc)
                elapsed_sec = (now - l_ts).total_seconds()
                if (
                    elapsed_sec < 15.0
                    and latest_sample.battery_percent == current_soc
                    and latest_sample.is_plugged_in == current_plugged
                    and latest_sample.is_user_active == is_user_active
                ):
                    should_insert_sample = False
                    sample_record = latest_sample

            if should_insert_sample:
                sample = TelemetrySample(
                    user_id=self.target_user_id,
                    timestamp=now,
                    battery_percent=current_soc,
                    is_plugged_in=current_plugged,
                    seconds_left=secs_left,
                    is_user_active=is_user_active,
                    idle_duration_seconds=round(idle_seconds, 1),
                    sleep_gap_seconds=round(sleep_gap_seconds, 1),
                    source=source_tag,
                )
                db.add(sample)
                db.commit()
                db.refresh(sample)
                sample_record = sample

            # Prune old samples to prevent unbounded database growth
            total_samples = db.query(TelemetrySample).filter(TelemetrySample.user_id == self.target_user_id).count()
            if total_samples > self.max_stored_samples:
                excess = total_samples - self.max_stored_samples
                subq = (
                    db.query(TelemetrySample.id)
                    .filter(TelemetrySample.user_id == self.target_user_id)
                    .order_by(TelemetrySample.timestamp.asc())
                    .limit(excess)
                    .all()
                )
                ids_to_del = [r[0] for r in subq]
                if ids_to_del:
                    db.query(TelemetrySample).filter(TelemetrySample.id.in_(ids_to_del)).delete(synchronize_session=False)
                    db.commit()

            # Update loop state
            self.last_plugged_state = current_plugged
            self.last_battery_percent = current_soc
            self.last_poll_time = now

            return {
                "success": True,
                "timestamp": now.isoformat().replace("+00:00", "Z"),
                "battery_percent": current_soc,
                "is_plugged_in": current_plugged,
                "seconds_left": secs_left,
                "is_user_active": is_user_active,
                "idle_duration_seconds": round(idle_seconds, 1),
                "sleep_gap_seconds": round(sleep_gap_seconds, 1),
                "active_session_id": self.active_session_id,
                "transition_event": transition_event,
                "sample_id": sample_record.id if sample_record else None,
            }

        except Exception as exc:
            logger.warning("Telemetry polling encountered an error: %s", str(exc), exc_info=True)
            db.rollback()
            return {
                "success": False,
                "error": str(exc),
                "timestamp": now.isoformat().replace("+00:00", "Z"),
            }
        finally:
            if should_close_session:
                db.close()

    def get_status(self, db: Optional[Session] = None) -> Dict[str, Any]:
        """
        Returns rich telemetry status metadata for the frontend dashboard:
        - Live battery reading
        - In-progress session info
        - Real sessions count and personalization progress (0-2: Learning, 3-6: Blended, 7+: Personalized)
        - Activity summary
        """
        should_close_session = False
        if db is None:
            db = SessionLocal()
            should_close_session = True

        try:
            # Query completed real sessions
            real_count = (
                db.query(ChargingSession)
                .filter(
                    ChargingSession.user_id == self.target_user_id,
                    ChargingSession.data_source == "REAL_WINDOWS",
                    ChargingSession.end_time.isnot(None),
                )
                .count()
            )

            # Determine personalization stage
            if real_count < 3:
                stage = "LEARNING"
            elif real_count < 7:
                stage = "BLENDED"
            else:
                stage = "PERSONALIZED"

            prog_pct = min(100.0, round((real_count / 7.0) * 100.0, 1))

            # Query active session info if open
            active_info = None
            if self.active_session_id is not None:
                sess = db.query(ChargingSession).filter(ChargingSession.id == self.active_session_id).first()
                if sess:
                    st = sess.start_time
                    if st.tzinfo is None:
                        st = st.replace(tzinfo=timezone.utc)
                    curr_dur = max(0.0, (datetime.now(timezone.utc) - st).total_seconds() / 60.0)
                    active_info = {
                        "session_id": sess.id,
                        "start_time": st.isoformat().replace("+00:00", "Z"),
                        "start_battery_percent": sess.start_battery_percent,
                        "current_battery_percent": self.last_battery_percent or sess.start_battery_percent,
                        "duration_minutes": round(curr_dur, 1),
                        "active_minutes": round(self.session_active_seconds / 60.0, 1),
                        "idle_minutes": round(self.session_idle_seconds / 60.0, 1),
                        "data_source": "REAL_WINDOWS",
                    }

            # Live hardware battery
            batt = device_battery_service.get_battery_status()

            last_poll_str = None
            if self.last_poll_time:
                lp = self.last_poll_time
                if lp.tzinfo is None:
                    lp = lp.replace(tzinfo=timezone.utc)
                last_poll_str = lp.isoformat().replace("+00:00", "Z")

            return {
                "collector_running": self.collector_running,
                "last_poll_time": last_poll_str,
                "poll_interval_seconds": self.poll_interval_seconds,
                "user_id": self.target_user_id,
                "device_battery": batt,
                "active_session": active_info,
                "real_sessions_count": real_count,
                "personalization_stage": stage,
                "personalization_progress_pct": prog_pct,
                "target_sessions_for_full_personalization": 7,
                "today_active_minutes": round(self.today_active_seconds / 60.0, 1),
                "today_idle_minutes": round(self.today_idle_seconds / 60.0, 1),
                "sleep_events_count": self.sleep_events_count,
                "privacy_notice": (
                    "Telemetry collects only aggregate battery levels and idle durations. "
                    "No keystrokes, screen contents, or personal files are recorded."
                ),
            }
        finally:
            if should_close_session:
                db.close()


# Global singleton service instance
telemetry_service = WindowsTelemetryService()
