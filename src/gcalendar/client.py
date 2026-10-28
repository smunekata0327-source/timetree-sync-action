
import json
import random
import time
from typing import ClassVar

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


class GoogleCalendarClient:
    SCOPES: ClassVar[list[str]] = [
        "https://www.googleapis.com/auth/calendar"
    ]

    MAX_RETRIES = 6
    WRITE_DELAY = 0.5

    def __init__(self, credentials_json: str):
        credentials_info = json.loads(credentials_json)

        credentials = service_account.Credentials.from_service_account_info(
            credentials_info,
            scopes=self.SCOPES,
        )

        self._service = build(
            "calendar",
            "v3",
            credentials=credentials,
        )

    def _execute(self, request, is_write=False):
        if is_write:
            time.sleep(self.WRITE_DELAY)

        for attempt in range(self.MAX_RETRIES + 1):
            try:
                return request.execute(num_retries=0)

            except HttpError as error:
                status = error.resp.status

                reason = ""
                try:
                    payload = json.loads(
                        error.content.decode("utf-8")
                    )
                    details = payload.get("error", {}).get(
                        "errors", []
                    )
                    if details:
                        reason = details[0].get("reason", "")
                except (ValueError, AttributeError, UnicodeDecodeError):
                    pass

                retryable = (
                    status in (429, 500, 502, 503, 504)
                    or (
                        status == 403
                        and reason in (
                            "rateLimitExceeded",
                            "userRateLimitExceeded",
                        )
                    )
                )

                if not retryable or attempt >= self.MAX_RETRIES:
                    raise

                delay = min(
                    2 ** attempt + random.uniform(0, 1),
                    64,
                )
                print(
                    f"Google API制限/一時エラー "
                    f"(HTTP {status}, {reason})。"
                    f"{delay:.1f}秒待って再試行します。"
                )
                time.sleep(delay)

    def get_calendar(self, calendar_id: str):
        request = self._service.calendars().get(
            calendarId=calendar_id
        )
        return self._execute(request)

    def create_event(self, calendar_id: str, event: dict):
        request = self._service.events().insert(
            calendarId=calendar_id,
            body=event,
        )
        return self._execute(request, is_write=True)

    def list_events(self, calendar_id: str):
        events = []
        page_token = None

        while True:
            request = self._service.events().list(
                calendarId=calendar_id,
                singleEvents=True,
                maxResults=2500,
                pageToken=page_token,
            )
            response = self._execute(request)
            events.extend(response.get("items", []))
            page_token = response.get("nextPageToken")
            if not page_token:
                break

        return events

    def update_event(
        self, calendar_id: str, event_id: str, event: dict
    ):
        request = self._service.events().update(
            calendarId=calendar_id,
            eventId=event_id,
            body=event,
        )
        return self._execute(request, is_write=True)

    def delete_event(self, calendar_id: str, event_id: str):
        request = self._service.events().delete(
            calendarId=calendar_id,
            eventId=event_id,
        )
        return self._execute(request, is_write=True)
