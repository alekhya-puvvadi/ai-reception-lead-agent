"""Demo leads that can be loaded without an API key, so the dashboard has something to show."""

from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from . import database as db

# (hours ago, transcript, record)
_SAMPLES = [
    (2, "Hi, I'm Rahul Sharma. I want to join the AI course. Please call me today after 6 PM on 9876501234.",
     dict(caller_name="Rahul Sharma", callback_number="9876501234", intent_type="admission", course_interest="AI",
          urgency="High", sentiment="Positive", lead_score=92, lead_score_reason="wants to join; asked for a call today",
          summary="Wants to join the AI course and asked for a callback today after 6 PM.",
          suggested_reply="Hi Rahul, thanks for your interest in our AI course. Our admissions team will call you today after 6 PM.",
          tags=["Admission", "AI", "Callback"])),
    (5, "Hello, I'm Anita Rao. I want to enrol in Data Science immediately. The batch starts Monday, right? Call me urgently at 9900112233.",
     dict(caller_name="Anita Rao", callback_number="9900112233", intent_type="admission", course_interest="Data Science",
          urgency="High", sentiment="Positive", lead_score=95, lead_score_reason="ready to enrol; batch starts Monday",
          summary="Wants to enrol in Data Science before Monday's batch and asked for an urgent call.",
          suggested_reply="Hi Anita, yes, the Data Science batch starts Monday. We will call you shortly to complete your enrolment.",
          tags=["Admission", "DataScience", "Urgent"])),
    (9, "Hi, this is Priya. I'm interested in the Python course. Could someone call me back sometime this week? My number is 9845012345.",
     dict(caller_name="Priya", callback_number="9845012345", intent_type="admission", course_interest="Python",
          urgency="Medium", sentiment="Positive", lead_score=74, lead_score_reason="interested in Python; wants a callback this week",
          summary="Interested in the Python course and wants a callback this week.",
          suggested_reply="Hi Priya, thanks for calling. We will phone you this week with details about the Python course.",
          tags=["Admission", "Python"])),
    (14, "I want to complain. The trainer has not come to class for the last three days and our exam is next week. Please fix this urgently.",
     dict(caller_name=None, callback_number=None, intent_type="complaint", course_interest=None, urgency="High",
          sentiment="Frustrated", lead_score=15, lead_score_reason="complaint, not a sales lead",
          summary="Reports that the trainer has missed three days of class with an exam next week.",
          suggested_reply="We are sorry about the missed classes. We are looking into this today and will confirm a trainer for your batch.",
          tags=["Complaint", "Trainer", "Urgent"])),
    (20, "Hello, I wanted to know the fees for the Cybersecurity course. Can you tell me?",
     dict(caller_name=None, callback_number=None, intent_type="fee_inquiry", course_interest="Cybersecurity",
          urgency="Low", sentiment="Neutral", lead_score=45, lead_score_reason="asked about fees only; no callback requested",
          summary="Asked about the fees for the Cybersecurity course.",
          suggested_reply="Thanks for your interest in Cybersecurity. Please share your number and we will send the fee details.",
          tags=["Fees", "Cybersecurity"])),
    (26, "Do you provide placement support after the Java full stack course? Which companies do you work with?",
     dict(caller_name=None, callback_number=None, intent_type="placement_inquiry", course_interest="Java Full Stack",
          urgency="Low", sentiment="Neutral", lead_score=50, lead_score_reason="asked about placements; no timeline",
          summary="Asked about placement support and hiring partners for Java Full Stack.",
          suggested_reply="Yes, we offer placement assistance after the course. We can share our hiring partner list if you leave your number.",
          tags=["Placement", "Java"])),
    (31, "I come from a low income family. Is there any government scheme or scholarship for IT training? Please call me back and explain.",
     dict(caller_name=None, callback_number=None, intent_type="scheme_eligibility", course_interest=None,
          urgency="Medium", sentiment="Neutral", lead_score=58, lead_score_reason="wants scheme details and a callback",
          summary="Asked which government schemes or scholarships are available and wants a callback.",
          suggested_reply="Thanks for asking. Our counsellor will call you to explain the schemes you may qualify for.",
          tags=["Scheme", "Scholarship"])),
    (40, "Hi, I just want to check what courses you offer. I'm only browsing for now.",
     dict(caller_name=None, callback_number=None, intent_type="general_query", course_interest=None, urgency="Low",
          sentiment="Neutral", lead_score=20, lead_score_reason="browsing; no follow-up requested",
          summary="Browsing the course list with no plan to join yet.",
          suggested_reply="Thanks for calling. You can see all our courses on our website, and we are happy to help whenever you are ready.",
          tags=["General"])),
]


def load_samples(db_path: Optional[Path] = None) -> int:
    """Insert the demo leads and return how many were added."""
    now = datetime.now()
    for hours_ago, transcript, record in _SAMPLES:
        created = (now - timedelta(hours=hours_ago)).isoformat(timespec="seconds")
        db.insert_call(transcript, record, source="sample", created_at=created, db_path=db_path)
    return len(_SAMPLES)
