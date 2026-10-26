# Evaluation report: text-v1

- Date: 2026-10-25T22:06:07
- Mode: text  |  Prompt: v1  |  Cases: 25
- Chat model: openai/gpt-oss-120b  |  Speech model: whisper-large-v3-turbo

## Results

| Metric | Value |
|---|---|
| Intent accuracy | 76.0% |
| Urgency accuracy | 72.0% |
| Name extraction accuracy | 100.0% |
| Phone extraction accuracy | 100.0% |
| Valid JSON on first attempt | 100.0% |
| Valid schema on first attempt | 100.0% |
| Pipeline success (usable record returned) | 100.0% |
| Invented name or phone (expected none) | 0 |
| Average latency | 1.639 s |

## By category

| Category | Cases | Intent | Urgency |
|---|---|---|---|
| accented | 4 | 50.0% | 75.0% |
| ambiguous | 6 | 33.3% | 83.3% |
| clear | 8 | 100.0% | 87.5% |
| multi_intent | 3 | 100.0% | 33.3% |
| noisy | 4 | 100.0% | 50.0% |

## Cases that failed (12 of 25)

**c03** (clear): intent expected `admission`, got `admission`; urgency expected `Medium`, got `High`
> Hi, this is Priya. I'm interested in the Python course. Could someone call me back sometime this week? My number is 9845012345.

**c10** (ambiguous): intent expected `general_query`, got `admission`; urgency expected `Low`, got `Low`
> Tell me about the cloud course.

**c11** (ambiguous): intent expected `general_query`, got `admission`; urgency expected `Low`, got `Low`
> Is the AI course good for someone with no background?

**c12** (ambiguous): intent expected `admission`, got `admission`; urgency expected `Low`, got `Medium`
> I'm thinking of joining but not sure yet, maybe next month. Can you send some details?

**c13** (ambiguous): intent expected `general_query`, got `admission`; urgency expected `Low`, got `Low`
> My friend studied here and said it's good. How does it work?

**c14** (ambiguous): intent expected `other`, got `general_query`; urgency expected `Low`, got `Low`
> Hello? Can you hear me? Is this the training centre? I wanted to ask about something.

**c15** (multi_intent): intent expected `admission`, got `admission`; urgency expected `Medium`, got `High`
> Hi, I'm Karthik. How much is the CCNA fee and do you guarantee a job after? If it's okay I'd like to join this month. Call me on 9123456780.

**c17** (multi_intent): intent expected `scheme_eligibility`, got `scheme_eligibility`; urgency expected `Low`, got `Medium`
> Are there scholarships for women in the cybersecurity course? And what would the fee be after the scholarship?

**c18** (noisy): intent expected `admission`, got `admission`; urgency expected `Medium`, got `High`
> hi uh my name is sunil I I want to join the python class ah call me nine eight seven six five four three two one zero

**c21** (noisy): intent expected `placement_inquiry`, got `placement_inquiry`; urgency expected `Medium`, got `High`
> hello my nam is meena i wan to know abot placment for data science cors plz cal back this week

**c22** (accented): intent expected `admission`, got `fee_inquiry`; urgency expected `High`, got `High`
> Sir namaskara, nanu Ramesh. Python course fees yeshtu sir? Nange tumba urgent, nale joining madbeku.

**c23** (accented): intent expected `fee_inquiry`, got `admission`; urgency expected `Low`, got `Medium`
> Hello madam, mujhe cybersecurity course ke baare mein jaanna hai. Fees kitni hai aur placement hota hai kya?

