"""One-off generator for golden_set.jsonl (kept for reference)."""
import json
A = [
 ("VPN says my token expired, how do I fix it?", "Scan the new QR code"),
 ("What does error VPN-403 mean?", "not in the remote-access group"),
 ("The VPN gateway keeps timing out, what should I try?", "retry on a different network"),
 ("What's the minimum password length?", "at least 14 characters"),
 ("How often do passwords expire?", "expire every 180 days"),
 ("Can I reuse an old password?", "last 10 passwords"),
 ("My laptop battery is swollen and hot, what do I do?", "stop using it immediately"),
 ("How do I ask for a new keyboard or monitor?", "submit the Hardware Request form"),
 ("How long until a requested monitor arrives?", "fulfilled within 5 business days"),
 ("Can I use text message codes for MFA?", "SMS codes are not allowed"),
 ("I lost my old phone and can't get MFA codes", "call the IT Service Desk on extension 5000"),
 ("How fast must I report a lost security key?", "within 2 hours"),
 ("What is the biggest attachment I can email?", "larger than 25 MB are blocked"),
 ("How do I report a phishing email?", "Report Phish"),
 ("How do I get a shared mailbox?", "Approval from the mailbox owner is required"),
 ("What do guests use for Wi-Fi?", "daily code from reception"),
 ("Can I install Zoom myself or do I need a ticket?", "installed from the Company Portal without a ticket"),
 ("How long does a software security review take?", "5 to 10 business days"),
 ("How long does temporary admin access last?", "lasts 4 hours"),
 ("My laptop might have malware, what should I do?", "disconnect it from the network but do not shut it down"),
 ("Who do I call about a security incident at night?", "extension 5999"),
 ("Can IT see my photos if I enroll my phone?", "does not give IT access to personal photos"),
 ("What screen lock does a BYOD phone need?", "screen lock of 6 digits or more"),
 ("Does the company back up my laptop?", "Laptops are not backed up"),
 ("How long can I recover deleted OneDrive files?", "recycle bin for 93 days"),
 ("When do I pick up my laptop on my first day?", "between 9:00 and 10:00 AM"),
 ("What is the deadline for security awareness training?", "within 7 days of joining"),
 ("What happens to my mailbox after I leave?", "retained for 90 days"),
 ("When are my accounts disabled on my last day?", "disabled at 6 PM"),
 ("How soon does my screen lock when working remotely?", "lock after 5 minutes of inactivity"),
 ("Where can I print in color?", "restricted to the second-floor printer"),
 ("When am I allowed to use Zoom?", "external customers only"),
 ("Are USB drives allowed?", "USB drives are blocked by default"),
 ("What are the Service Desk hours?", "Monday to Friday from 8:00 AM to 8:00 PM IST"),
 ("How quickly is a Priority 1 issue answered?", "response within 30 minutes"),
 ("How do I get access to my department's shared drive?", "approved or rejected within 2 business days"),
 ("Can I paste customer data into a public AI chatbot?", "Never paste Confidential data into public AI chat tools"),
 ("Can I use public Wi-Fi at a cafe while working?", "only when the VPN is connected"),
]
U = [
 "What is the company's parental leave policy?",
 "How do I submit an expense report for travel?",
 "How do I set up a Linux workstation with dual boot?",
 "How do I reset my forgotten Windows login password?",
 "Which VPN protocol does the gateway use, OpenVPN or WireGuard?",
 "How do I back up my personal photos from my phone?",
 "What are the cafeteria opening hours?",
 "Does the company provide a corporate credit card?",
 "How do I fix a blue screen error on my laptop?",
 "How do I enable dark mode in Outlook?",
]
with open("golden_set.jsonl", "w") as f:
    for q, s in A:
        f.write(json.dumps({"question": q, "answerable": True, "gold_snippet": s}) + "\n")
    for q in U:
        f.write(json.dumps({"question": q, "answerable": False}) + "\n")
print(len(A), "answerable +", len(U), "unanswerable")
