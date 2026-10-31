from django.db import migrations

TEMPLATES = [
    ("Auto-reply: thanks for your message", "auto_reply",
     "Thanks for reaching out, {{ first_name }}!",
     "Hi {{ first_name }},\n\n"
     "Thank you for contacting me about \"{{ subject }}\". This is a quick note to confirm your message arrived safely.\n\n"
     "I personally read every message and will get back to you within 24 hours (usually much sooner). "
     "If it's urgent, you can reply to this email directly.\n\n"
     "In the meantime, feel free to look through my recent work: {{ website }}/portfolio/"),
    ("Reply: project inquiry, next steps", "reply",
     "Re: {{ subject }}",
     "Hi {{ first_name }},\n\n"
     "Thanks so much for getting in touch — your project sounds great and I'd love to help.\n\n"
     "To give you an accurate plan and quote, could you share a little more about:\n"
     "1. Your main goal (more leads, sales, brand awareness…)\n"
     "2. Your timeline\n"
     "3. Your approximate budget\n"
     "4. Any websites or competitors you like\n\n"
     "If it's easier, we can also jump on a free 20-minute call — just tell me a time that suits you.\n\n"
     "Looking forward to working together!"),
    ("Reply: send proposal / quote", "reply",
     "Your proposal from Marketian — {{ subject }}",
     "Hi {{ first_name }},\n\n"
     "Thank you for the details. Based on our conversation, here's what I recommend:\n\n"
     "Scope:\n- \n- \n- \n\n"
     "Timeline: \n"
     "Investment: \n\n"
     "This includes regular progress updates and a final report. "
     "If everything looks good, just reply \"Approved\" and I'll send the next steps to get started."),
    ("Reply: follow-up", "reply",
     "Following up: {{ subject }}",
     "Hi {{ first_name }},\n\n"
     "I wanted to follow up on my previous message about \"{{ subject }}\". "
     "Do you have any questions, or is there anything I can clarify?\n\n"
     "Happy to adjust the plan to fit your needs."),
    ("Reply: polite decline", "reply",
     "Re: {{ subject }}",
     "Hi {{ first_name }},\n\n"
     "Thank you for thinking of me for this project. Unfortunately I'm not able to take it on right now, "
     "as my schedule is fully booked.\n\n"
     "I'd be glad to help in the future — please don't hesitate to reach out again. Wishing you every success!"),
    ("General: introduce my services", "general",
     "Helping {{ name }} grow online",
     "Hi {{ first_name }},\n\n"
     "I'm {{ my_name }}, {{ my_role }} at Marketian. I help businesses grow with SEO, paid ads, "
     "social media and high-converting websites.\n\n"
     "You can see some of my recent results here: {{ website }}/portfolio/\n\n"
     "Would you be open to a short call to see if I can help you too?"),
]


def create_defaults(apps, schema_editor):
    EmailSignature = apps.get_model("mailer", "EmailSignature")
    EmailTemplate = apps.get_model("mailer", "EmailTemplate")
    if not EmailSignature.objects.exists():
        EmailSignature.objects.create(label="Default", is_default=True)
    if not EmailTemplate.objects.exists():
        for name, purpose, subject, body in TEMPLATES:
            EmailTemplate.objects.create(name=name, purpose=purpose, subject=subject, body=body)


class Migration(migrations.Migration):
    dependencies = [("mailer", "0001_initial")]
    operations = [migrations.RunPython(create_defaults, migrations.RunPython.noop)]
