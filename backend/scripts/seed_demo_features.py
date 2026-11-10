"""Run with manage.py shell after seed_course_demo; preserve existing demo work."""

from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from accounts.models import User
from announcements.models import Announcement
from departments.models import Department
from library_reservations.models import StudyRoom
from program_outcomes.models import ProgramOutcome
from student_feedback.consent_services import publish_sharing, request_sharing, respond_to_sharing
from student_feedback.discussion_services import add_comment, cast_vote
from student_feedback.models import Feedback
from student_feedback.services import reply_privately, submit_feedback


@transaction.atomic
def seed_features():
    if not settings.DEBUG:
        raise RuntimeError("Demo fixtures are for local development only.")
    cse = Department.objects.get(code="CSE")
    ee = Department.objects.get(code="EE")
    student = User.objects.get(email="ali.yilmaz@obs.test")
    peer = User.objects.get(email="zeynep.ak@obs.test")
    teacher = User.objects.get(email="cengiz.riva@obs.test")
    head = User.objects.get(email="head.cse@obs.test")

    for department, titles in [
        (cse, ["Engineering problem analysis", "Software design and evaluation"]),
        (ee, ["Electrical circuit analysis", "Experimental measurement and interpretation"]),
    ]:
        for number, title in enumerate(titles, start=1):
            ProgramOutcome.objects.get_or_create(
                department=department, code=f"PO{number}",
                defaults={"title": title, "description": f"Demonstrate {title.lower()} using appropriate engineering methods.",
                          "display_order": number},
            )

    for suffix in ["A", "B"]:
        StudyRoom.objects.get_or_create(name=f"Library Study Room {suffix}", defaults={"location": "Library, first floor"})

    for author, channel, title, body in [
        (head, "OFFICIAL", "Demo: Course registration", "Review your term plan and send your selection to your advisor."),
        (teacher, "OFFICIAL", "Demo: Teaching office hours", "Bring your questions about this week's examples to office hours."),
        (student, "STUDENT", "Demo: Study group", "Would anyone like to review programming exercises together?"),
    ]:
        Announcement.objects.get_or_create(
            author=author, channel=channel, title=title,
            defaults={"body": body, "status": "PUBLISHED", "published_at": timezone.now()},
        )

    def feedback(title, body, audience="INSTRUCTOR", recipient=teacher):
        existing = Feedback.objects.filter(student=student, title=title).first()
        if existing is not None:
            return existing, False
        return submit_feedback(student, {
            "title": title, "body": body, "audience": audience,
            "instructor": recipient, "is_anonymous": True,
        }), True

    feedback("Demo: More practical examples", "Could we work through another practical example in class?")
    feedback("Demo: Laboratory access", "Could the department review laboratory opening hours?", "HEAD", None)
    conditions = {"visible_to_students": True, "visible_to_heads": True, "reveal_identity": False,
                  "show_results_to_students": True, "show_comments_to_students": True}

    source, created = feedback("Demo: Weekly review session", "A weekly review session would help us consolidate the material.")
    if created:
        proposal = request_sharing(source.pk, teacher, {
            **conditions, "introduction": "Would a review session be useful for other students?",
            "poll_question": "Would you attend a weekly review session?", "poll_options": ["Yes", "No"],
            "poll_closes_at": timezone.now() + timedelta(days=7),
        })
        respond_to_sharing(proposal.pk, student, {"action": "approve"})
        publish_sharing(proposal.pk, teacher)
        add_comment(proposal.pk, peer, "A short session with worked examples would be useful.")
        add_comment(proposal.pk, teacher, "Thank you; we can review the most common questions.")
        cast_vote(proposal.pk, student, 0)
        cast_vote(proposal.pk, peer, 0)

    source, created = feedback("Demo: Feedback for a teaching head", "Could we discuss an additional tutorial?", recipient=head)
    if created:
        request_sharing(source.pk, head, {**conditions, "introduction": "May I ask the department's students for their views?"})

    source, created = feedback("Demo: Keep this conversation private", "I would prefer to discuss this suggestion privately.")
    if created:
        proposal = request_sharing(source.pk, teacher, conditions)
        respond_to_sharing(proposal.pk, student, {"action": "reject"})
        reply_privately(source.pk, teacher, "Understood. We can continue this conversation here.")

    print("Demo feature fixtures are ready. Existing forms, consent, votes and content were preserved.")


seed_features()
