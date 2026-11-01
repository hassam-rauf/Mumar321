// Records the demo video: drives demo/chat.html against the running webhook server.
// Usage: node demo/record_demo.js http://localhost:8787 <order_number>   -> demo/out/*.webm
const { chromium } = require("playwright");
const [, , BASE = "http://localhost:8787", ORDER = "1"] = process.argv;
const sleep = ms => new Promise(r => setTimeout(r, ms));

(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 720 },
                                         recordVideo: { dir: __dirname + "/out", size: { width: 1280, height: 720 } } });
  const page = await ctx.newPage();
  await page.goto(BASE + "/");
  await sleep(500);

  const say = async (text, wait = 2200) => {
    await page.click("#in");
    await page.keyboard.type(text, { delay: 45 });
    await sleep(250);
    await page.keyboard.press("Enter");
    await sleep(wait);
  };
  const scene = async (caption) => { await page.evaluate(c => { demo.clear(); demo.caption(c); }, caption); await sleep(900); };
  const card = (t, s, ms) => page.evaluate(([t, s, ms]) => demo.card(t, s, ms), [t, s, ms]);

  await card("WooCommerce AI Support Agent",
    "Working prototype of the 4 flows: order tracking · taking orders · inventory · business-hours call routing\n\n" +
    "Chat window = simple test client (Voiceflow does this part in production)\n" +
    "Backend = same logic as the Make scenario · Store data = local mock store in WooCommerce REST API v3 format", 7000);

  await scene("1/4  Order tracking");
  await say("Where is my order?", 1600);
  await say(`#${ORDER}`, 1600);
  await say("sara.lee@example.com", 5000);

  await scene("1/4  Order tracking — wrong email");
  await say("Where is my order?", 1600);
  await say(ORDER, 1600);
  await say("someone@else.com", 4500);

  await scene("2/4  Inventory check");
  await say("Do you have the trucker cap in stock?", 3800);
  await say("Is the hoodie in stock?", 3500);
  await say("Medium", 4000);
  await say("What about large?", 4200);

  await scene("3/4  Taking an order");
  await say("I want to order 1 large hoodie", 1700);
  await say("Jane Roe", 1600);
  await say("jane@example.com", 1600);
  await say("+1 555 0110", 2600);
  await say("Yes", 6000);

  await scene("4/4  Call routing — outside business hours");
  await sleep(1500);
  await say("Can I talk to someone?", 4500);
  await say("Jane Roe", 1600);
  await say("+1 555 0110", 1600);
  await say("Question about a bulk order", 4500);

  await scene("4/4  Call routing — inside business hours (hours changed to 24/7)");
  await page.click("#h-open");
  await sleep(2500);
  await say("Can I talk to someone?", 5000);

  await card("Next: the same flows in your bot",
    "Your Voiceflow agent + Make scenario, on both Woo sites, every path tested\n\n" +
    "Code, Make guide & Voiceflow config: github.com/hassam-rauf/Mumar321", 6000);

  const video = page.video();
  await ctx.close();
  console.log(await video.path());
  await browser.close();
})();
