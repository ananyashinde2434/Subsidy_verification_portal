SUBSIDY_MAX_AMOUNT = 12000

import os
import re
from ocr_engine import run_ocr, clean_text
from file_handler import normalize_to_images


import unicodedata

def normalize_digits(text):
    out = ""
    for ch in text:
        if ch.isdigit():
            try:
                out += str(unicodedata.digit(ch))
            except:
                out += ch
        else:
            out += ch
    return out

print("Running from:", os.getcwd())


# ---------------- DOCUMENT CLASSIFICATION ----------------

def classify_document_type(text):
    text = text.lower()
    if "neft" in text and "statement" not in text:
        return "NEFT_ACK"

    if "upi" in text or "google pay" in text:
        return "UPI_RECEIPT"
    return "UNKNOWN"


def looks_like_bank_statement(text):
    text = text.lower()
    keywords = [
        "opening balance",
        "closing balance",
        "transaction details",
        "dr",
        "cr",
        "statement between"
    ]

    score = 0
    for k in keywords:
        if k in text:
            score += 1

    return score >= 2


# ---------------- BANK STATEMENT ROW EXTRACTION ----------------

def extract_statement_transactions(text):
    transactions = []

    text = text.lower()
    text = re.sub(r"\s+", " ", text)

    pattern = re.findall(
        r"(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{4}).{0,200}?(\d{3,}(?:,\d{3})*(?:\.\d{2})?)",
        text
    )

    for date, amount in pattern:
        transactions.append({
            "date": date,
            "amount": float(amount.replace(",", ""))
        })

    return transactions


# ---------------- FIELD EXTRACTION ----------------

def extract_amount(text):
    match = re.search(r"(₹|rs\.?|र)\s*\d+[,.]?\d*", text)
    if match:
        return match.group(0)

    match = re.search(r"\b\d{1,3}(,\d{3})+\b", text)
    if match:
        return match.group(0)

    match = re.search(r"(amount|paid|completed)\D{0,15}\d+", text)
    if match:
        return match.group(0)

    return None


def extract_transaction_fields(cleaned_text):
    cleaned_text = cleaned_text.lower()

    extracted_data = {
        "amount": None,
        "transaction_id": None,
        "date": None,
        "mode": None,
        "bank": None
    }

    extracted_data["amount"] = extract_amount(cleaned_text)

    match = re.search(
        r"(utr\/rrn|utr|rrn|txn\s*id|transaction\s*id)\s*no\.?\s*[:\-]?\s*(\d{6,})",
        cleaned_text
    )
    if match:
        extracted_data["transaction_id"] = match.group(2)

    match = re.search(
        r"(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{4})|(\d{1,2}\s*(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\s*\d{4})",
        cleaned_text
    )
    if match:
        extracted_data["date"] = match.group(0)

    if "upi" in cleaned_text:
        extracted_data["mode"] = "UPI"
    elif "imps" in cleaned_text:
        extracted_data["mode"] = "IMPS"
    elif "neft" in cleaned_text:
        extracted_data["mode"] = "NEFT"

    banks = [
        "state bank of india",
        "bank of baroda",
        "hdfc",
        "icici",
        "axis",
        "google pay",
        "phonepe",
        "paytm"
    ]

    for bank in banks:
        if bank in cleaned_text:
            extracted_data["bank"] = bank
            break

    return extracted_data


def build_evidence(extracted_data, doc_type):
    return {
        "has_amount": bool(extracted_data.get("amount")),
        "has_date": bool(extracted_data.get("date")),
        "has_txn_id": bool(extracted_data.get("transaction_id")),
        "has_mode": bool(extracted_data.get("mode")),
        "doc_type": doc_type
    }


def compute_confidence(evidence):
    score = 0.0

    if evidence["has_amount"]:
        score += 0.4
    if evidence["has_date"]:
        score += 0.3
    if evidence["has_txn_id"]:
        score += 0.2
    if evidence["has_mode"]:
        score += 0.1

    return round(score, 2)

# ---------------- VALIDATION ----------------

def validate_extracted_data(extracted_data, doc_type):
    evidence = build_evidence(extracted_data, doc_type)
    confidence = compute_confidence(evidence)

    validation_result = {
        "is_transaction": confidence >= 0.6,
        "confidence_score": confidence,
        "missing_fields": [],
        "is_valid_structure": confidence >= 0.6
    }

    if not evidence["has_amount"]:
        validation_result["missing_fields"].append("amount")
    if not evidence["has_date"]:
        validation_result["missing_fields"].append("date")
    if not evidence["has_txn_id"]:
        validation_result["missing_fields"].append("transaction_id")

    return validation_result


def make_final_decision(validation_result):
    score = validation_result.get("confidence_score", 0)

    if score >= 0.75:
        return {
            "final_status": "Valid",
            "reason": "High confidence transaction proof"
        }

    if score >= 0.5:
        return {
            "final_status": "Needs Review",
            "reason": "Partial transaction evidence"
        }

    return {
        "final_status": "Invalid",
        "reason": "Insufficient transaction evidence"
    }



# ---------------- MAIN PIPELINE ----------------

def process_document(file_path):
    images = normalize_to_images(file_path)
    raw_text = run_ocr(images)
    cleaned_text = clean_text(raw_text)
    cleaned_text = normalize_digits(cleaned_text)


    # 🔴 FIRST: BANK STATEMENT DETECTION (MUST BE FIRST)
    if looks_like_bank_statement(cleaned_text):
        doc_type = "BANK_STATEMENT"
    else:
        doc_type = classify_document_type(cleaned_text)

    extracted_data = extract_transaction_fields(cleaned_text)

    if doc_type == "BANK_STATEMENT":
        rows = extract_statement_transactions(cleaned_text)

        filtered_rows = [
            row for row in rows
            if row["amount"] <= SUBSIDY_MAX_AMOUNT
        ]

        if filtered_rows:
            validation_result = {
                "is_transaction": True,
                "missing_fields": [],
                "is_valid_structure": True
            }
        else:
            validation_result = {
                "is_transaction": False,
                "missing_fields": ["no_transaction_upto_12000"],
                "is_valid_structure": False
            }
    else:
        validation_result = validate_extracted_data(extracted_data, doc_type)

    final_decision = make_final_decision(validation_result)

    return {
        "document_type": doc_type,
        "extracted_data": extracted_data,
        "validation_result": validation_result,
        "final_decision": final_decision
    }


# ---------------- RUN ----------------

if __name__ == "__main__":
    file_path = r"D:\cse\academics\coding\intern projects\invoice\WhatsApp Image 2026-01-04 at 23.02.55.jpeg"
    result = process_document(file_path)
    print(result)
