# 📖 Cerberus AI Operational Standard Operating Procedure (SOP)

Operator manual and safety officer reference for daily control room triage, worker compliance verification, and zone rule configuration.

---

## 🖥️ Daily Operator Workflow

### 1. Live Surveillance & Stream Focus (`/live`)
- The multi-camera wall provides high-level situational awareness.
- **Focus Stream Mode:** Click any stream tile to expand it to high-frame-rate focus view for close inspection of worker behavior.

### 2. Incident Verification & Triage (`/violations`)
- Every detected safety violation is assigned a status (`unacknowledged`, `accepted`, or `declined`).
- **Accept Alert:** Validates the breach as a true incident and logs it to compliance records.
- **Decline Alert:** Marks transient false positives and automatically deletes spurious evidence.

### 3. Worker Compliance Scorecards & Proof Gallery (`/compliance`)
- Review individual personnel safety records, hours tracked, and aggregate compliance percentage.
- **Visual Evidence Inspection:** Click any timeline thumbnail to open the high-resolution snapshot modal showing detected PPE vs missing PPE tags.
- **Selective Violation Purging:** Select specific violation records using checkboxes and click **"Delete Selected"** to remove erroneous alerts while automatically updating the worker's compliance score.

### 4. Safety Zone Policy Enforcement (`/zones`)
- Adjust required PPE per operational area:
  - **High-Risk Height Zones:** Enforce hard hats, reflective vests, and safety harnesses.
  - **Machinery Floor:** Enforce ear protection and safety glasses.
- Adjust temporal debounce thresholds ($\ge 8/10$ window with a 2-second dwell floor).
