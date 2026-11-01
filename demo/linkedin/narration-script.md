# LinkedIn video: narration script

Read each part when the video reaches its start time. Speak softly and slowly (about 2 words per second). Each part has a little spare time, so there is no need to rush.

**0:00 - 0:15** (intro)

> This is an AI support agent for a WooCommerce store. It tracks orders, checks stock, takes new orders, and routes calls based on business hours. Let me show you how it works.

**0:15 - 0:34** (track)

> First, order tracking. The customer shares an order number and their email. The agent checks the store's API, and replies with the status, the items, and the tracking number. On the right, you can see each request behind the scenes.

**0:34 - 0:46** (wrong)

> If the email doesn't match the order, the agent gives a polite, general answer. That way, nobody can look up someone else's order.

**0:46 - 1:07** (stock)

> Next, inventory. The agent reads live stock levels. For products with sizes, it checks each size separately, which is a very common source of mistakes.

**1:07 - 1:26** (order)

> The agent can also take an order. It collects the customer's details, confirms them, checks stock, and creates a pending order in WooCommerce.

**1:26 - 1:45** (closed)

> Outside business hours, the call isn't transferred. Instead, the agent takes a callback request: name, phone number, and the reason for the call.

**1:45 - 1:56** (open)

> During business hours, the same request goes straight to a human. The hours and the timezone are simple settings, not hard-coded.

**1:56 - 2:15** (outro)

> This demo runs on a test store. In production, Voiceflow handles the conversation, and Make runs this same logic. I'm Hassam Rauf, and I build AI agents and automations for businesses. If you'd like one for your store, let's talk.
