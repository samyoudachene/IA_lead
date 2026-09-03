"""
=====================================
  AI LEAD GENERATION AGENT — VERSION GRATUITE
  Groq (gratuit) + Google Custom Search (gratuit) + Gmail
=====================================
"""

import os
import time
import csv
import smtplib
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# ─── CONFIG ───────────────────────────────────────────────────────
GROQ_API_KEY          = os.getenv("GROQ_API_KEY")
GOOGLE_API_KEY        = os.getenv("GOOGLE_API_KEY")       # Custom Search
GOOGLE_SEARCH_ENGINE  = os.getenv("GOOGLE_SEARCH_ENGINE_ID")
EMAIL_SENDER          = os.getenv("EMAIL_SENDER")
EMAIL_PASSWORD        = os.getenv("EMAIL_PASSWORD")

CRM_FILE = "clients.csv"


# ─── COULEURS TERMINAL ────────────────────────────────────────────
class C:
    BLUE   = "\033[94m"
    GREEN  = "\033[92m"
    YELLOW = "\033[93m"
    RED    = "\033[91m"
    CYAN   = "\033[96m"
    BOLD   = "\033[1m"
    END    = "\033[0m"

def log(msg, color=C.CYAN):
    t = datetime.now().strftime("%H:%M:%S")
    print(f"{color}[{t}] {msg}{C.END}")


# ─── ÉTAPE 1 : CHERCHER LES CLIENTS ──────────────────────────────
def search_clients(query: str, city: str, max_results: int = 10):
    """
    Cherche des businesses via Google Custom Search (gratuit)
    Extrait nom, site web, description depuis les résultats
    """
    log(f"🔍 Recherche: '{query}' dans '{city}'", C.BLUE)

    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        "key": GOOGLE_API_KEY,
        "cx":  GOOGLE_SEARCH_ENGINE,
        "q":   f"{query} {city} موقع",
        "num": min(max_results, 10),
        "hl":  "ar"
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        data = response.json()

        if "error" in data:
            log(f"❌ Erreur Google Search: {data['error']['message']}", C.RED)
            return []

        items = data.get("items", [])
        results = []

        for item in items:
            # Extraire le domaine du site
            link = item.get("link", "")
            domain = ""
            if link:
                parts = link.replace("https://", "").replace("http://", "").split("/")
                domain = parts[0] if parts else ""

            client = {
                "name":       item.get("title", "").split("-")[0].split("|")[0].strip(),
                "website":    link,
                "domain":     domain,
                "description": item.get("snippet", ""),
                "address":    city,
                "phone":      "",
                "email":      extract_email_from_snippet(item.get("snippet", "")),
                "type":       query,
                "rating":     "N/A",
                "status":     "nouveau",
                "date_found": datetime.now().strftime("%Y-%m-%d")
            }
            results.append(client)

            has_site = "✅" if domain else "❌"
            log(f"  {has_site} {client['name'][:40]} | {domain or 'Pas de site'}", C.GREEN)

        # Chercher aussi les businesses SANS site web
        results += search_no_website(query, city, max_results)

        log(f"📊 Total trouvé: {len(results)} clients", C.GREEN)
        return results[:max_results]

    except Exception as e:
        log(f"❌ Erreur réseau: {e}", C.RED)
        return []


def search_no_website(query: str, city: str, max_results: int = 5):
    """
    Cherche spécifiquement les businesses sans site web
    (cible principale = clients qui ont le plus besoin de toi)
    """
    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        "key": GOOGLE_API_KEY,
        "cx":  GOOGLE_SEARCH_ENGINE,
        "q":   f"{query} {city} site:facebook.com OR site:instagram.com -site:web",
        "num": min(max_results, 10),
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        items = data.get("items", [])
        results = []
        for item in items:
            client = {
                "name":        item.get("title", "").split("-")[0].split("|")[0].strip(),
                "website":     "",
                "domain":      "",
                "description": item.get("snippet", ""),
                "address":     city,
                "phone":       "",
                "email":       extract_email_from_snippet(item.get("snippet", "")),
                "type":        query,
                "rating":      "N/A",
                "status":      "nouveau",
                "date_found":  datetime.now().strftime("%Y-%m-%d")
            }
            results.append(client)
        return results
    except:
        return []


def extract_email_from_snippet(text: str) -> str:
    """Extrait un email si présent dans le texte"""
    import re
    match = re.search(r'[\w.+-]+@[\w-]+\.[\w.]+', text)
    return match.group(0) if match else ""


# ─── ÉTAPE 2 : ANALYSER ──────────────────────────────────────────
def analyze_client(client: dict) -> dict:
    score   = 50
    reasons = []

    if not client.get("website"):
        score += 40
        reasons.append("❌ Pas de site web — client prioritaire")
    elif "facebook" in client.get("website", "") or "instagram" in client.get("website", ""):
        score += 30
        reasons.append("📱 Présence réseaux sociaux seulement — besoin d'un vrai site")
    else:
        score += 5
        reasons.append("✅ A un site web")

    if client.get("email"):
        score += 10
        reasons.append("📧 Email trouvé")

    client["priority_score"] = min(score, 100)
    client["analysis"] = " | ".join(reasons)
    return client


# ─── ÉTAPE 3 : GÉNÉRER MESSAGE AVEC GROQ (GRATUIT) ───────────────
def generate_message(client: dict, your_service: str, your_name: str) -> str:
    """
    Utilise Groq API (llama3 - 100% gratuit) pour générer les messages
    """
    has_website = bool(client.get("website"))
    only_social = has_website and (
        "facebook" in client.get("website", "") or
        "instagram" in client.get("website", "")
    )

    if not has_website:
        situation = "ليس لديهم موقع إلكتروني على الإطلاق"
    elif only_social:
        situation = "لديهم فقط صفحة على وسائل التواصل الاجتماعي، بدون موقع رسمي"
    else:
        situation = f"لديهم موقع إلكتروني: {client['website']}"

    prompt = f"""أنت خبير في التسويق الرقمي. اكتب رسالة تواصل احترافية وقصيرة (5-6 جمل) باللغة العربية.

معلومات العميل:
- الاسم: {client['name']}
- النوع: {client['type']}
- المدينة: {client['address']}
- الوضع الرقمي: {situation}

أنت تقدم: {your_service}
اسمك: {your_name}

قواعد:
1. ابدأ بالتحية باسم المؤسسة
2. أظهر أنك تعرف وضعهم الحالي
3. اشرح الفائدة المباشرة لهم (ليس لك)
4. اختم بطلب موعد قصير
5. لا تكن مبالغاً — كن مباشراً ومحترفاً
6. اكتب الرسالة فقط، بدون أي شرح أو مقدمة"""

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    body = {
        "model": "llama3-70b-8192",   # Modèle gratuit et puissant
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 400,
        "temperature": 0.7
    }

    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers,
            json=body,
            timeout=30
        )
        data = response.json()
        return data["choices"][0]["message"]["content"].strip()

    except Exception as e:
        log(f"❌ Erreur Groq: {e}", C.RED)
        return (
            f"مرحباً {client['name']}،\n\n"
            f"لاحظنا أنكم لا تمتلكون حضوراً رقمياً قوياً على الإنترنت، "
            f"في حين أن عملاءكم يبحثون عنكم يومياً.\n\n"
            f"نحن متخصصون في {your_service}، ويمكننا مساعدتكم في "
            f"استقطاب عملاء جدد عبر الإنترنت.\n\n"
            f"هل يمكننا تحديد موعد قصير لعرض ما يمكننا تقديمه لكم؟\n\n"
            f"مع تحياتي،\n{your_name}"
        )


# ─── ÉTAPE 4 : ENVOYER EMAIL ──────────────────────────────────────
def send_email(to_email: str, subject: str, message: str, client_name: str) -> bool:
    if not to_email or "@" not in to_email:
        log(f"⚠️  Pas d'email pour {client_name}", C.YELLOW)
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = EMAIL_SENDER
        msg["To"]      = to_email

        html = f"""
        <html>
        <body dir="rtl" style="font-family:Arial,sans-serif;font-size:15px;
                               color:#222;line-height:1.9;max-width:600px;
                               margin:auto;padding:24px;">
          <div style="border-right:4px solid #0066cc;padding-right:16px;">
            {message.replace(chr(10), '<br>')}
          </div>
          <hr style="border:none;border-top:1px solid #eee;margin:20px 0">
          <p style="color:#aaa;font-size:11px;">
            للإلغاء الاشتراك، يرجى الرد بكلمة "إلغاء"
          </p>
        </body></html>
        """
        msg.attach(MIMEText(message, "plain", "utf-8"))
        msg.attach(MIMEText(html, "html", "utf-8"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.sendmail(EMAIL_SENDER, to_email, msg.as_string())

        log(f"📧 Email envoyé → {client_name} ({to_email})", C.GREEN)
        return True

    except Exception as e:
        log(f"❌ Échec envoi → {client_name}: {e}", C.RED)
        return False


# ─── CRM ─────────────────────────────────────────────────────────
def save_to_crm(clients: list):
    if not clients:
        return
    fieldnames = [
        "name", "address", "phone", "email", "website",
        "type", "priority_score", "analysis", "status", "date_found"
    ]
    file_exists = os.path.exists(CRM_FILE)
    with open(CRM_FILE, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        if not file_exists:
            writer.writeheader()
        writer.writerows(clients)
    log(f"💾 {len(clients)} clients sauvegardés dans '{CRM_FILE}'", C.GREEN)


# ─── AGENT PRINCIPAL ──────────────────────────────────────────────
def run_agent(
    search_query: str,
    city: str,
    your_service: str,
    your_name: str,
    send_emails: bool = False,
    max_results: int = 10
):
    print(f"\n{C.BOLD}{'='*55}")
    print(f"    🤖  AI LEAD AGENT — VERSION GRATUITE")
    print(f"    Groq (gratuit) + Google Custom Search")
    print(f"{'='*55}{C.END}\n")

    # 1. Chercher
    clients = search_clients(search_query, city, max_results)
    if not clients:
        log("Aucun client trouvé. Vérifie tes clés API dans le fichier .env", C.RED)
        return

    # 2. Analyser
    clients = [analyze_client(c) for c in clients]
    clients.sort(key=lambda x: x["priority_score"], reverse=True)

    print()
    log("🧠 Génération des messages avec Groq (llama3)...", C.YELLOW)

    for i, client in enumerate(clients, 1):
        print(f"\n{C.BOLD}{'─'*45}")
        print(f"  Client {i}/{len(clients)}: {client['name'][:40]}")
        print(f"{'─'*45}{C.END}")
        log(f"Score: {client['priority_score']}/100", C.CYAN)
        log(f"Analyse: {client['analysis']}", C.CYAN)

        # 3. Générer message
        message = generate_message(client, your_service, your_name)
        print(f"\n{C.YELLOW}📝 Message:{C.END}")
        print(f"{C.GREEN}{message}{C.END}")

        # 4. Envoyer email
        if send_emails and client.get("email"):
            subject = f"عرض خاص لـ {client['name']} - {your_service}"
            sent = send_email(client["email"], subject, message, client["name"])
            client["status"] = "envoyé" if sent else "échec"
        else:
            client["status"] = "message_prêt"

        time.sleep(0.5)  # Pause courte (Groq est très rapide)

    # 5. Sauvegarder
    print()
    save_to_crm(clients)

    # Résumé
    print(f"\n{C.BOLD}{'='*55}")
    print(f"  📊 RÉSUMÉ")
    print(f"{'='*55}{C.END}")
    print(f"  ✅ Clients analysés       : {len(clients)}")
    print(f"  🎯 Sans site web          : {sum(1 for c in clients if not c.get('website'))}")
    print(f"  📧 Avec email trouvé      : {sum(1 for c in clients if c.get('email'))}")
    print(f"  💾 CRM sauvegardé dans    : {CRM_FILE}")
    print(f"  💰 Coût total             : 0€ 🎉")
    print(f"{'='*55}\n")


# ─── LANCEMENT ────────────────────────────────────────────────────
if __name__ == "__main__":

    run_agent(
        search_query = "مطاعم",                              # ← Ce que tu cherches
        city         = "الجزائر العاصمة",                    # ← Ville
        your_service = "تصميم مواقع إلكترونية احترافية",
        your_name    = "فريق WebPro",
        send_emails  = False,                               # ← True = envoi réel
        max_results  = 8
    )
