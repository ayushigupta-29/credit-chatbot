# Credit Score Driver Reference

This document lists every factor tracked in our bureau data that affects a credit score.
For each factor, both directions of change are explicitly stated.
Do not infer or assume the opposite of any statement — both directions are written out here.

---

## Payment Delinquency (DPD / NPA / Write-off)

### DPD 30+ (last 12m)
- **If this value increases:** Bad for score
- **If this value decreases:** Good for score
- A DPD flag means at least one payment was 30+ days late in the last 12 months. Having this flag (value = 1) is bad. Clearing it (1 → 0) is good. Setting it (0 → 1) is bad.

### DPD 60+ (last 24m)
- **If this value increases:** Bad for score
- **If this value decreases:** Good for score
- A DPD 60+ flag means at least one payment was 60+ days late in the last 24 months. Clearing it improves the score. Setting it lowers the score.

### DPD 90+ (last 36m)
- **If this value increases:** Bad for score
- **If this value decreases:** Good for score
- A DPD 90+ flag means at least one payment was 90+ days late in the last 36 months. Clearing it improves the score. Setting it lowers the score.

### NPA account
- **If this value increases:** Bad for score
- **If this value decreases:** Good for score
- An NPA flag means at least one account has been classified as non-performing. Clearing it is good. Setting it is bad.

### Write-off / settlement
- **If this value increases:** Bad for score
- **If this value decreases:** Good for score
- A write-off/settlement flag means a lender wrote off a debt or accepted a partial settlement. Clearing it improves the score. Setting it lowers the score.

### No. of DPD 30+ incidents (12m)
- **If this value increases:** Bad for score
- **If this value decreases:** Good for score
- The count of DPD 30+ incidents (not just whether one exists). More incidents means more missed payments — worse. Fewer incidents means payment behaviour is improving.

## Credit Utilisation and Outstanding Balance

### CC/OD utilisation
- **If this value increases:** Bad for score
- **If this value decreases:** Good for score
- Credit utilisation is the % of available credit limit currently used. Lower is better (ideally under 30%). Higher utilisation signals financial stress. A decrease is good; an increase is bad.

### Total outstanding balance
- **If this value increases:** Bad for score
- **If this value decreases:** Good for score
- Total outstanding balance across all loans and cards. A decrease means debt is being paid down, which is positive. An increase means more debt, which can be negative.

## Credit Enquiries

### Enquiries (last 12m)
- **If this value increases:** Bad for score
- **If this value decreases:** Good for score
- Same as enquiries last 6 months but over a 12-month window. Fewer enquiries is better.

### Enquiries (last 6m)
- **If this value increases:** Bad for score
- **If this value decreases:** Good for score
- Each loan or card application triggers a hard enquiry. More enquiries in 6 months signals credit-seeking behaviour and lowers the score. Fewer enquiries is better.

## Account Counts

### Active accounts
- **If this value increases:** Good for score
- **If this value decreases:** No effect
- More active accounts shows ongoing credit management. An increase is positive. A decrease has no standard effect — it could mean a loan was paid off (neutral-positive) or a card was closed (slightly negative).

### Total accounts
- **If this value increases:** Good for score
- **If this value decreases:** Bad for score
- More accounts (over time) shows experience managing different types of credit. An increase is generally positive. A sharp decrease means accounts were closed, which can hurt credit mix and age.
