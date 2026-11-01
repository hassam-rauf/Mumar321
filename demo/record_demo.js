// Records the demo video: drives demo/chat.html against the running webhook server.
// Usage: node demo/record_demo.js http://localhost:8787 <order_number>
//   MODE=linkedin  -> narration-paced scenes, personal intro/outro, writes demo/out/scenes.json
const { chromium } = require("playwright");
const fs = require("fs");
const [, , BASE = "http://localhost:8787", ORDER = "1"] = process.argv;
const LINKEDIN = process.env.MODE === "linkedin";
const NARR = LINKEDIN ? require("./narration.json") : {};
const WPS = 2.3; // narration pace, words per second
const sleep = ms => new Promise(r => setTimeout(r, ms));
const minMs = key => (NARR[key] ? (NARR[key].split(/\s+/).length / WPS + 1.4) * 1000 : 0);

(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 720 },
                                         recordVideo: { dir: __dirname + "/out", size: { width: 1280, height: 720 } } });
  const page = await ctx.newPage();
  const t0 = Date.now();
  const scenes = [];
  await page.goto(BASE + "/");
  await sleep(500);

  const say = async (text, wait = 2200) => {
    await page.click("#in");
    await page.keyboard.type(text, { delay: 45 });
    await sleep(250);
    await page.keyboard.press("Enter");
    await sleep(wait);
  };
  // Runs one scene; in LinkedIn mode it lasts at least as long as its narration.
  const scene = async (key, caption, body) => {
    const start = Date.now();
    scenes.push({ key, start: (start - t0) / 1000 });
    if (caption) { await page.evaluate(c => { demo.clear(); demo.caption(c); }, caption); await sleep(900); }
    await body();
    const left = minMs(key) - (Date.now() - start);
    if (left > 0) await sleep(left);
  };
  const card = (t, s, ms) => page.evaluate(([t, s, ms]) => demo.card(t, s, ms), [t, s, ms]);

  if (LINKEDIN) {
    await scene("intro", null, () => card("AI Support Agent for WooCommerce",
      "Order tracking · Inventory · Taking orders · Business-hours call routing\n\nWorking prototype by Hassam Rauf", minMs("intro")));
  } else {
    await card("WooCommerce AI Support Agent",
      "Working prototype of the 4 flows: order tracking · taking orders · inventory · business-hours call routing\n\n" +
      "Chat window = simple test client (Voiceflow does this part in production)\n" +
      "Backend = same logic as the Make scenario · Store data = local mock store in WooCommerce REST API v3 format", 7000);
  }

  await scene("track", "1/4  Order tracking", async () => {
    await say("Where is my order?", 1600);
    await say(`#${ORDER}`, 1600);
    await say("sara.lee@example.com", 5000);
  });

  await scene("wrong", "1/4  Order tracking — wrong email", async () => {
    await say("Where is my order?", 1600);
    await say(ORDER, 1600);
    await say("someone@else.com", 4500);
  });

  await scene("stock", "2/4  Inventory check", async () => {
    await say("Do you have the trucker cap in stock?", 3800);
    await say("Is the hoodie in stock?", 3500);
    await say("Medium", 4000);
    await say("What about large?", 4200);
  });

  await scene("order", "3/4  Taking an order", async () => {
    await say("I want to order 1 large hoodie", 1700);
    await say("Jane Roe", 1600);
    await say("jane@example.com", 1600);
    await say("+1 555 0110", 2600);
    await say("Yes", 6000);
  });

  await scene("closed", "4/4  Call routing — outside business hours", async () => {
    await sleep(1500);
    await say("Can I talk to someone?", 4500);
    await say("Jane Roe", 1600);
    await say("+1 555 0110", 1600);
    await say("Question about a bulk order", 4500);
  });

  await scene("open", "4/4  Call routing — inside business hours (hours changed to 24/7)", async () => {
    await page.click("#h-open");
    await sleep(2500);
    await say("Can I talk to someone?", 5000);
  });

  if (LINKEDIN) {
    await scene("outro", null, () => card("Hassam Rauf",
      "AI Agents · Chatbots · Automation · WooCommerce · Python\n\n" +
      "Demo on a test store. The chat window stands in for Voiceflow.\n" +
      "Code & docs: github.com/hassam-rauf/Mumar321", minMs("outro")));
  } else {
    await card("Next: the same flows in your bot",
      "Your Voiceflow agent + Make scenario, on both Woo sites, every path tested\n\n" +
      "Code, Make guide & Voiceflow config: github.com/hassam-rauf/Mumar321", 6000);
  }

  scenes.push({ key: "end", start: (Date.now() - t0) / 1000 });
  const video = page.video();
  await ctx.close();
  fs.writeFileSync(__dirname + "/out/scenes.json", JSON.stringify(scenes, null, 2));
  console.log(await video.path());
  await browser.close();
})();
