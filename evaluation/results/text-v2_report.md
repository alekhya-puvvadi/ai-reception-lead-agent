# Evaluation report: text-v2

- Date: 2026-10-25T22:02:37
- Mode: text  |  Prompt: v2  |  Cases: 25
- Chat model: openai/gpt-oss-120b  |  Speech model: whisper-large-v3-turbo

## Results

| Metric | Value |
|---|---|
| Intent accuracy | 92.0% |
| Urgency accuracy | 72.0% |
| Name extraction accuracy | 100.0% |
| Phone extraction accuracy | 100.0% |
| Valid JSON on first attempt | 100.0% |
| Valid schema on first attempt | 100.0% |
| Pipeline success (usable record returned) | 100.0% |
| Invented name or phone (expected none) | 0 |
| Average latency | 2.842 s |

## By category

| Category | Cases | Intent | Urgency |
|---|---|---|---|
| accented | 4 | 75.0% | 75.0% |
| ambiguous | 6 | 83.3% | 66.7% |
| clear | 8 | 100.0% | 87.5% |
| multi_intent | 3 | 100.0% | 33.3% |
| noisy | 4 | 100.0% | 75.0% |

## Cases that failed (8 of 25)

**c02** (clear): intent expected `fee_inquiry`, got `fee_inquiry`; urgency expected `Low`, got `Medium`
> Hello, I wanted to know the fees for the Cybersecurity course. Can you tell me?

**c09** (ambiguous): intent expected `complaint`, got `complaint`; urgency expected `Medium`, got `High`
> Hi, I called yesterday about the course but nobody told me anything.

**c12** (ambiguous): intent expected `admission`, got `admission`; urgency expected `Low`, got `Medium`
> I'm thinking of joining but not sure yet, maybe next month. Can you send some details?

**c14** (ambiguous): intent expected `other`, got `general_query`; urgency expected `Low`, got `Low`
> Hello? Can you hear me? Is this the training centre? I wanted to ask about something.

**c15** (multi_intent): intent expected `admission`, got `admission`; urgency expected `Medium`, got `High`
> Hi, I'm Karthik. How much is the CCNA fee and do you guarantee a job after? If it's okay I'd like to join this month. Call me on 9123456780.

**c17** (multi_intent): intent expected `scheme_eligibility`, got `scheme_eligibility`; urgency expected `Low`, got `Medium`
> Are there scholarships for women in the cybersecurity course? And what would the fee be after the scholarship?

**c20** (noisy): intent expected `fee_inquiry`, got `fee_inquiry`; urgency expected `Low`, got `Medium`
> fees for java course how much [inaudible] java

**c23** (accented): intent expected `fee_inquiry`, got `general_query`; urgency expected `Low`, got `Medium`
> Hello madam, mujhe cybersecurity course ke baare mein jaanna hai. Fees kitni hai aur placement hota hai kya?

