# Synthetic Dataset Design

Fictional company: **Werkstein Industrietechnik GmbH** - mid-sized German precision engineering company.
Two bank accounts: `werkstein-db-eur` (Deutsche Bank), `werkstein-vrb-eur` (Volksbank).
All IBANs, company names, and references are fictional.

## Counterparties

### Customers (AR - they pay us)
| ID | Name | Country | IBAN |
|----|------|---------|------|
| C1001 | Bergmann Verpackungen GmbH | DE | DE72500105176412345678 |
| C1002 | Bergmann Packaging Danmark A/S | DK | DK9520000987654321 |
| C1003 | Nordland Papier AG | DE | DE44200505501098765432 |
| C1004 | Kastner Wellpappe GmbH | AT | AT611904300234567890 |
| C1005 | Europrint Solutions B.V. | NL | NL18RABO0300065432 |
| C1006 | Fabrica Carton S.A. | ES | ES9121000418450200012345 |
| C1007 | Polskie Opakowania Sp. z o.o. | PL | PL61109010140000071219812345 |
| C1008 | Helvetia Packaging AG | CH | CH3908704016075473007 |
| C1009 | Druckhaus Weber GmbH | DE | DE91300606010012345678 |
| C1010 | Muller Display GmbH & Co. KG | DE | DE85370502990012345678 |
| C1011 | Scandinavia Pack AB | SE | SE3550000000054910123456 |
| - | Kastner Packaging Polska Sp. z o.o. | PL | PL27114020040000300201355387 |
| - | Hartmann Industriebedarf e.K. | DE | DE23100500000012345678 |

### Suppliers (AP - we pay them)
| ID | Name | Country |
|----|------|---------|
| S2001 | Rheinland Leasing GmbH & Co. KG | DE |
| S2002 | Stahl & Metall Handel GmbH | DE |
| S2003 | Technoglas Industriebedarf GmbH | DE |
| S2004 | Buroservice Krause GmbH | DE |
| S2005 | Energie Sudwest AG | DE |
| S2006 | Grundstucksverwaltung Hofmann GbR | DE |
| S2007 | Logistik Express GmbH | DE |
| S2008 | Schmid Werkzeugbau GmbH | DE |

---

## Case Mapping

### Case 1: Perfect Match (amount + reference match exactly)
| Bank TX | Invoice | Amount | Notes |
|---------|---------|--------|-------|
| BT-001 | INV-001 (RE-2026-0001) | 4,250.00 | Bergmann, direct ref |
| BT-002 | INV-002 (RE-2026-0002) | 1,890.50 | Nordland, "/INV/" prefix |
| BT-003 | INV-003 (RE-2026-0003) | 7,612.80 | Kastner, "Rg." prefix + date |
| BT-004 | INV-004 (RE-2026-0004) | 2,340.00 | Europrint, direct ref |
| BT-005 | INV-010 (RE-2026-0010) | 5,200.00 | Druckhaus Weber |
| BT-006 | INV-011 (RE-2026-0012) | 3,175.40 | Scandinavia Pack |
| BT-031 | INV-036 (SI-240015) | 3,450.00 | AP: Stahl & Metall |
| BT-032 | INV-037 (SI-240018) | 892.40 | AP: Technoglas |
| BT-033 | INV-038 (SI-240020) | 156.78 | AP: Buroservice |
| BT-034 | INV-039 (SX-780234) | 4,280.00 | AP: Schmid |
| BT-046 | INV-048 (SI-240030) | 1,350.00 | AP: Logistik Express |
| BT-047 | INV-049 (SI-240032) | 2,156.80 | AP: Technoglas |
| BT-048 | INV-039b (SX-780290) | 890.00 | AP: Schmid (no invoice! see Case 7) |

### Case 2: Skonto / Cash Discount (bank amount < invoice, discount noted)
| Bank TX | Invoice | Invoice Amt | Paid Amt | Discount | Notes |
|---------|---------|-------------|----------|----------|-------|
| BT-007 | INV-005 (RE-2026-0005) | 3,800.00 | 3,724.00 | 2% (76.00) | Mueller Display, "Sk." in ref |
| BT-008 | INV-006 (RE-2026-0006) | 12,500.00 | 12,250.00 | 2% (250.00) | Helvetia, "2% Skonto" in ref |
| BT-009 | INV-007 (RE-2026-0007) | 7,000.00 | 6,860.00 | 2% (140.00) | Bergmann, "Sk. 140,00" |
| BT-010 | INV-012 (RE-2026-0013) | 3,000.00 | 2,940.00 | 2% (60.00) | Nordland, "2% Skonto" |
| BT-035 | INV-040 (SI-240022) | 2,800.00 | 2,744.00 | 2% (56.00) | AP: Logistik Express |
| BT-036 | INV-041 (SI-240025) | 5,900.00 | 5,782.00 | 2% (118.00) | AP: Stahl & Metall |

### Case 3: Batch Payment (one bank TX references multiple invoices)
| Bank TX | Invoices | Total | Notes |
|---------|----------|-------|-------|
| BT-011 (9,450.00) | INV-008 (3,150) + INV-009 (4,200) + INV-013 (2,100) | 9,450.00 | Bergmann, 3 invoices listed in ref |
| BT-012 (6,720.50) | INV-014 (3,200) + INV-015 (3,520.50) | 6,720.50 | Fabrica Carton, amounts listed in ref |
| BT-013 (4,890.00) | INV-016 (1,500) + INV-017 (2,100) + INV-018 (1,290) | 4,890.00 | Polskie, 3 refs listed |
| BT-014 (8,340.20) | INV-019 (2,800) + INV-020 (3,140.20) + INV-021 (2,400) | 8,340.20 | Kastner, 3 refs listed |
| BT-037 (1,245.60) | INV-042 (415.20) + INV-043 (415.20) + INV-044 (415.20) | 1,245.60 | AP: Rheinland Leasing, 3 lease contracts |
| BT-038 (4,890.00) | INV-045 (1,630) + INV-046 (1,630) + INV-047 (1,630) | 4,890.00 | AP: Energie, 3 months prepaid |

### Case 4: Vague / No Invoice Reference (requires counterparty + amount matching)
| Bank TX | Possible Invoices | Notes |
|---------|-------------------|-------|
| BT-015 (5,670.00) | INV-022 (3,270) + INV-023 (2,400) = 5,670 | Europrint, ref="VARIOUS INVOICES" - sum matches exactly |
| BT-016 (3,200.00) | INV-024 (3,200) | Polskie, ref="SAMMELZAHLUNG JANUAR" - amount matches |
| BT-017 (4,100.00) | INV-034 (4,250) closest but 150 off | Fabrica Carton, ref="DIVERSE FAKTUREN" - no exact match! Ambiguous. |

### Case 5: Name Mismatch / Entity Resolution
| Bank TX | Bank Name | Invoice Name | Notes |
|---------|-----------|--------------|-------|
| BT-007 | "Muller Display GmbH + Co. KG" | "Muller Display GmbH & Co. KG" | umlaut missing in bank, & vs + |
| BT-012 | "FABRICA CARTON SA" | "Fabrica Carton S.A." | ALL CAPS, no accent, no dots |
| BT-018 | "MUELLER DISPLAY GMBH + CO. KG" | "Muller Display GmbH & Co. KG" | ALL CAPS, ue vs u-umlaut, + vs & |
| BT-019 | "FABRICA CARTON SA" | "Fabrica Carton S.A." | Same mismatch as BT-012 |
| BT-049 | "STAHL U. METALL HANDEL GMBH" | "Stahl & Metall Handel GmbH" | ALL CAPS, "U." vs "&" |

### Case 6: Invoice Marked Paid in ERP but NO Bank Transaction
| Invoice | Amount | ERP Says Paid | Bank Match |
|---------|--------|---------------|------------|
| INV-032 (RE-2026-0034) | 4,100.00 | Yes, 2026-01-12 | NONE - ghost payment |
| INV-033 (RE-2026-0035) | 2,850.00 | Yes, 2026-01-18 | NONE - ghost payment |

Agent should flag: "ERP shows these as paid but no corresponding bank receipt found."

### Case 7: Bank Payment with NO Matching Invoice
| Bank TX | Amount | Notes |
|---------|--------|-------|
| BT-020 | 1,750.00 | Druckhaus Weber "VORAUSZAHLUNG PROJEKT 4712" - advance payment, no invoice |
| BT-021 | 980.00 | Hartmann Industriebedarf - completely unknown customer, not in ERP |
| BT-022 | 5,400.00 | Bergmann Packaging Danmark - proforma reference, no invoice |
| BT-039 | 5,720.00 | Rent payment - operational, no invoice in system |
| BT-040 | 890.00 | Utility costs Q4 - operational |
| BT-041 | 178.50 | Rheinland Leasing - separate lease contract, no invoice |
| BT-042-044 | various | Bank fees - no invoices |
| BT-045 | 45,890.00 | Salary batch - no invoice |
| BT-048 | 890.00 | Schmid Werkzeugbau SX-780290 - no matching invoice |
| BT-050 | 340.00 | Buroservice Krause SI-240038 - no matching invoice |

### Case 8: Partial Payment (bank amount significantly less than invoice)
| Bank TX | Invoice | Invoice Amt | Paid | Remaining | Notes |
|---------|---------|-------------|------|-----------|-------|
| BT-023 | INV-027 (RE-2026-0028) | 6,000.00 | 3,000.00 | 3,000.00 | "Teilzahlung 1/2" - installment 1 of 2 |
| BT-024 | INV-028 (RE-2026-0029) | 9,000.00 | 4,500.00 | 4,500.00 | "1. Rate" - first installment |
| BT-025 | INV-029 (RE-2026-0030) | 5,250.00 | 2,100.00 | 3,150.00 | "Abschlagszahlung" - progress payment |

### Case 9: Duplicate Payment (same invoice paid twice)
| Bank TX 1 | Bank TX 2 | Invoice | Amount | Notes |
|-----------|-----------|---------|--------|-------|
| BT-004 (Jan 9, DB) | BT-026 (Jan 20, VRB) | INV-004 (RE-2026-0004) | 2,340.00 | Same ref, different bank accounts, 11 days apart |
| BT-005 (Jan 15, DB) | BT-027 (Jan 22, VRB) | INV-010 (RE-2026-0010) | 5,200.00 | Same ref, different bank accounts, 7 days apart |

Agent should flag: "Invoice RE-2026-0004 appears to have been paid twice (total 4,680.00 vs invoice 2,340.00)."

### Case 10: Cross-Entity / Subsidiary Payment
| Bank TX | Paying Entity | Invoice Entity | Invoice | Notes |
|---------|---------------|----------------|---------|-------|
| BT-028 | Bergmann Packaging Danmark A/S (DK) | Bergmann Verpackungen GmbH (DE) | INV-030 (RE-2026-0031) | Danish subsidiary pays German parent's invoice |
| BT-029 | Kastner Packaging Polska Sp. z o.o. (PL) | Kastner Wellpappe GmbH (AT) | INV-035 (RE-2026-0032) | Polish subsidiary pays Austrian parent's invoice |

Agent must recognize these are related entities (same group name pattern).

### Case 11: AP Leasing Batch (already covered under Case 3)
BT-037 -> 3 Rheinland Leasing invoices (INV-042, INV-043, INV-044)

### Case 12: Late Payment (significant delay past due date)
| Bank TX | Invoice | Due Date | Payment Date | Days Late |
|---------|---------|----------|-------------|-----------|
| BT-030 | INV-031 (RE-2026-0033) | 2025-12-15 | 2026-01-30 | 46 days |

---

## Summary Statistics

- **Bank transactions:** 50 (30 CREDIT, 20 DEBIT)
- **Invoices:** 50 (35 AR, 15 AP)
- **Perfect matches:** 12
- **Skonto matches:** 6
- **Batch payments:** 6 (covering ~18 invoices)
- **Vague reference:** 3 (1 exact sum match, 1 single match, 1 ambiguous)
- **Name mismatches:** 5
- **Ghost payments (ERP only):** 2
- **Unmatched bank transactions:** 10
- **Partial payments:** 3
- **Duplicate payments:** 2
- **Cross-entity:** 2
- **Late payments:** 1

## Expected Agent Behavior

The reconciliation agent should:
1. Match ~12 transactions trivially by exact reference + amount
2. Recognize ~6 skonto payments as valid (amount difference = stated discount)
3. Split ~6 batch payments across their constituent invoices
4. Use counterparty + amount sum heuristics for ~3 vague-reference payments
5. Resolve ~5 name mismatches using fuzzy matching / entity resolution
6. Flag 2 ghost payments (ERP paid, no bank evidence)
7. Flag 10 bank transactions with no invoice match
8. Flag 3 partial payments with outstanding balances
9. Flag 2 duplicate payments as potential overpayments
10. Recognize 2 cross-entity payments (subsidiary pays parent's invoice)
11. Flag 1 severely late payment (46 days overdue)
