// Records the simulated phone-call demo: drives demo/voice_call.html against the running webhook server.
// Usage: DEMO_MODE=1 FORCE_ROUTE=message python3 scripts/webhook_server.py &
//        node demo/record_voice_demo.js http://localhost:8787 <order_number>
//        python3 demo/build_voice_demo.py        -> demo/vapi/voice-agent-demo.mp4 with voices
// Each line is spoken with ffmpeg's built-in flite TTS (agent: slt, caller: rms). The text on screen
// is paced to the clip length, and demo/out/voice/timeline.json records when each clip starts.
const { chromium } = require("playwright");
const { execFileSync } = require("child_process");
const fs = require("fs");
const path = require("path");
const [, , BASE = "http://localhost:8787", ORDER = "1"] = process.argv;
const sleep = ms => new Promise(r => setTimeout(r, ms));
const VOICE_DIR = path.join(__dirname, "out", "voice");
const VOICES = { agent: "slt", caller: "rms" };

// Make text easier for a TTS engine to read; the screen still shows the original text.
function spoken(text) {
  return text
    .replace(/([\w.+-]+)@([\w-]+)\.(\w+)/g, (_, u, d, t) => `${u.replace(/\./g, " dot ")} at ${d} dot ${t}`)
    .replace(/Tracking: (\w+) \w*(\d{4})\./, "Tracking: $1, number ending in $2.")
    .replace(/\$(\d+)\.00/g, "$1 dollars").replace(/\$(\d+)\.(\d\d)/g, "$1 dollars $2")
    .replace(/#(\d+)/g, "number $1")
    .replace(/Mon-Fri 09:00-17:00 \(America\/New_York\)/, "Monday to Friday, 9 AM to 5 PM, New York time")
    .replace(/\+1 555 0110/g, "plus one, five five five, zero one one zero")
    .replace(/\b1 x /g, "one ").replace(/\(|\)/g, ",");
}

function synth(i, who, text) {
  fs.mkdirSync(VOICE_DIR, { recursive: true });
  const txt = path.join(VOICE_DIR, `${String(i).padStart(2, "0")}.txt`);
  const wav = txt.replace(/\.txt$/, ".wav");
  fs.writeFileSync(txt, spoken(text));
  execFileSync("ffmpeg", ["-loglevel", "error", "-y", "-f", "lavfi", "-i",
    `flite=textfile=${txt}:voice=${VOICES[who]}`, "-ar", "44100", wav]);
  const dur = parseFloat(execFileSync("ffprobe", ["-v", "error", "-show_entries", "format=duration",
    "-of", "csv=p=0", wav]).toString());
  return { wav, dur };
}

(async () => {
  fs.rmSync(VOICE_DIR, { recursive: true, force: true });
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 720 },
                                         recordVideo: { dir: __dirname + "/out", size: { width: 1280, height: 720 } } });
  const page = await ctx.newPage();
  const t0 = Date.now(); // the recording starts with the page
  const timeline = [];
  await page.goto(BASE + "/voice");
  const d = (fn, ...args) => page.evaluate(([fn, args]) => demo[fn](...args), [fn, args]);
  const say = async (who, text) => {
    const { wav, dur } = synth(timeline.length, who, text);
    const words = text.split(" ").length;
    timeline.push({ start: (Date.now() - t0) / 1000, wav, dur, who });
    await d("speak", who, text, words / Math.max(dur - 0.2, 0.5));
  };

  await d("card", "AI Phone Agent for WooCommerce",
          "Tracks orders · checks live stock · takes callbacks\nBuilt on Vapi tools + the WooCommerce REST API", 3800);
  await d("start");
  await d("caption", "Call starts");
  await say("agent", "Hi, thanks for calling the store! I can track an order, check stock, take an order, or connect you to our team. How can I help?");

  await d("caption", "1/3 Order tracking");
  await say("caller", `Hi, where's my order? It's number ${ORDER}, and my email is sara.lee@example.com.`);
  await say("agent", "One moment, let me pull up that order.");
  await say("agent", await d("tool", "track_order", { order_number: ORDER, email: "sara.lee@example.com" }));

  await d("caption", "2/3 Live stock with sizes");
  await say("caller", "Great, thanks. Do you have the zip hoodie?");
  await say("agent", await d("tool", "check_stock", { product_name: "hoodie" }));
  await say("caller", "Large, please.");
  await say("agent", await d("tool", "check_stock", { product_name: "hoodie", option: "L" }));

  await d("caption", "3/3 After hours → callback");
  await say("caller", "Can I talk to someone about a bulk order?");
  await say("agent", await d("tool", "business_hours", {}));
  await say("caller", "Sure. Jane Roe, +1 555 0110. It's about a bulk order.");
  await say("agent", await d("tool", "callback_request", { name: "Jane Roe", phone: "+1 555 0110", reason: "Bulk order" }));
  await say("agent", "Thanks for calling. Have a great day!");
  await d("caption", "Call ended");
  await sleep(1200);

  await d("card", "Hassam Rauf · AI Agent & Automation Developer",
          "Voice agents · RAG chatbots · n8n / Make automations\nWant one for your store? Let's talk.", 4200);
  fs.writeFileSync(path.join(VOICE_DIR, "timeline.json"), JSON.stringify(timeline, null, 2));
  await ctx.close();
  await browser.close();
})();
