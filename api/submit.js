// Student news / event suggestion endpoint — Vercel serverless function.
//
// WIRING (when the domain + Resend account are ready):
//   1. vercel env add RESEND_API_KEY <key from resend.com → API keys>  (production + preview)
//   2. vercel env add SUBMIT_TO <inbox that receives submissions, e.g. the family gmail>
//   3. vercel env add SUBMIT_FROM <sender on your VERIFIED resend domain, e.g. hello@yourdomain>
//      (unset → falls back to resend's testing sender onboarding@resend.dev,
//       which can only deliver to your own resend-account email)
//   4. push — auto-deploys.
// Until RESEND_API_KEY + SUBMIT_TO exist this returns 503 with a friendly error;
// the site shows the same message in the dialog. No mailto fallback by design.
//
// Anti-spam: honeypot field ("website") + hard length caps. Stateless, so no
// rate limiting — add Cloudflare Turnstile to the form if it's ever abused.

export default async function handler(req, res) {
  res.setHeader("Cache-Control", "no-store");
  if (req.method !== "POST") {
    res.statusCode = 405;
    return res.json({ error: "POST only" });
  }

  let d = {};
  try {
    d = (req.body && typeof req.body === "object") ? req.body : JSON.parse(req.body || "{}");
  } catch {
    d = {};
  }
  if (d.website) return res.json({ ok: true });   // honeypot: pretend success, deliver nothing

  const type = d.type === "event" ? "event" : "student";
  const clean = s => String(s ?? "").slice(0, 4000).trim();
  const name = clean(d.name).slice(0, 80);
  const title = clean(d.title).slice(0, 120);
  const body = clean(d.body);
  if (!title || !body) {
    res.statusCode = 400;
    return res.json({ error: "A headline and some details, please!" });
  }

  const key = process.env.RESEND_API_KEY;
  const to = process.env.SUBMIT_TO;
  const from = process.env.SUBMIT_FROM || "onboarding@resend.dev";
  if (!key || !to) {
    res.statusCode = 503;
    return res.json({ error: "Submissions aren't wired up yet — check back soon!" });
  }

  try {
    const r = await fetch("https://api.resend.com/emails", {
      method: "POST",
      headers: { "Authorization": `Bearer ${key}`, "Content-Type": "application/json" },
      body: JSON.stringify({
        from,
        to: [to],
        subject: (type === "student" ? "[student news] " : "[event idea] ") + title,
        text: `From: ${name || "anonymous"}\nType: ${type}\n\n${title}\n\n${body}\n`
      })
    });
    if (!r.ok) {
      res.statusCode = 502;
      return res.json({ error: "The mail service didn't accept that — please try again in a bit." });
    }
    return res.json({ ok: true });
  } catch {
    res.statusCode = 502;
    return res.json({ error: "The mail service didn't accept that — please try again in a bit." });
  }
}
