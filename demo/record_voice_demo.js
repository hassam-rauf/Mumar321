// Records the simulated phone-call demo: drives demo/voice_call.html against the running webhook server.
// Usage: DEMO_MODE=1 FORCE_ROUTE=message python3 scripts/webhook_server.py &
//        node demo/record_voice_demo.js http://localhost:8787 <order_number>
// Output: demo/out/*.webm (convert with ffmpeg, see docs/vapi-setup.md)
const { chromium } = require("playwright");
const [, , BASE = "http://localhost:8787", ORDER = "1"] = process.argv;
const sleep = ms => new Promise(r => setTimeout(r, ms));

(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 720 },
                                         recordVideo: { dir: __dirname + "/out", size: { width: 1280, height: 720 } } });
  const page = await ctx.newPage();
  await page.goto(BASE + "/voice");
  const d = (fn, ...args) => page.evaluate(([fn, args]) => demo[fn](...args), [fn, args]);

  await d("card", "AI Phone Agent for WooCommerce",
          "Tracks orders · checks live stock · takes callbacks\nBuilt on Vapi tools + the WooCommerce REST API", 3800);
  await d("start");
  await d("caption", "Call starts");
  await d("speak", "agent", "Hi, thanks for calling the store! I can track an order, check stock, take an order, or connect you to our team. How can I help?");

  await d("caption", "1/3 Order tracking");
  await d("speak", "caller", `Hi, where's my order? It's number ${ORDER}, and my email is sara.lee@example.com.`);
  await d("speak", "agent", "One moment, let me pull up that order.");
  let said = await d("tool", "track_order", { order_number: ORDER, email: "sara.lee@example.com" });
  await d("speak", "agent", said);

  await d("caption", "2/3 Live stock with sizes");
  await d("speak", "caller", "Great, thanks. Do you have the zip hoodie?");
  said = await d("tool", "check_stock", { product_name: "hoodie" });
  await d("speak", "agent", said);
  await d("speak", "caller", "Large, please.");
  said = await d("tool", "check_stock", { product_name: "hoodie", option: "L" });
  await d("speak", "agent", said);

  await d("caption", "3/3 After hours → callback");
  await d("speak", "caller", "Can I talk to someone about a bulk order?");
  said = await d("tool", "business_hours", {});
  await d("speak", "agent", said);
  await d("speak", "caller", "Sure. Jane Roe, plus one five five five, zero one one zero. It's about a bulk order.");
  said = await d("tool", "callback_request", { name: "Jane Roe", phone: "+1 555 0110", reason: "Bulk order" });
  await d("speak", "agent", said);
  await d("speak", "agent", "Thanks for calling. Have a great day!");
  await d("caption", "Call ended");
  await sleep(1200);

  await d("card", "Hassam Rauf · AI Agent & Automation Developer",
          "Voice agents · RAG chatbots · n8n / Make automations\nWant one for your store? Let's talk.", 4200);
  await ctx.close();
  await browser.close();
})();
