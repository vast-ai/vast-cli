"""Drive the page in headless Chrome against the fake Vast API and worker. Not run by pytest:

    pip install playwright   # once; uses the installed Chrome
    python tests/cli/serverless_ui/e2e_page.py [screenshot dir] [chrome path]

Checks the flows end to end (streaming chat, multi-turn, SDK view, images, burst, media,
worker errors) and that the key never reaches the DOM or browser storage. Fails on any
console error, which includes CSP violations.
"""
import asyncio, json, sys, tempfile
import aiohttp
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE)]
from aiohttp import web
from playwright.async_api import async_playwright
import fake_vast
from vastai.serverless.ui import server as ui

SHOTS = sys.argv[1] if len(sys.argv) > 1 else tempfile.mkdtemp(prefix="serverless-ui-e2e-")
# An installed Chrome if there is one, else Playwright's own (`playwright install chromium`)
CHROME = sys.argv[2] if len(sys.argv) > 2 else next(
    (c for c in ("/usr/bin/google-chrome", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
     if Path(c).exists()), None)

def serve_ui(app):
    """A runner for the UI as `vastai run serverless-ui` runs it: a client that goes away
    cancels its request."""
    return web.AppRunner(app, handler_cancellation=True)


async def until(check, timeout=15):
    for _ in range(int(timeout * 20)):
        if await check():
            return
        await asyncio.sleep(0.05)
    raise TimeoutError("condition not met")


async def main():
    state = fake_vast.initial_state()
    state["instances_hidden"] = True  # workers start with no address; found on a later lookup
    ui.HOSTS_EVERY = 0.5
    fake = web.AppRunner(fake_vast.make_app(state)); await fake.setup()
    await web.TCPSite(fake, "127.0.0.1", 8811).start()
    base = "http://127.0.0.1:8811"
    async def plain_ssl(): import ssl; return ssl.create_default_context()
    ui.vast_ssl_context = plain_ssl
    plain = serve_ui(ui.make_app(base, autoscaler_url=base)); await plain.setup()
    await web.TCPSite(plain, "127.0.0.1", 8812).start()
    keyed = serve_ui(ui.make_app(base, autoscaler_url=base, api_key=fake_vast.KEY))
    await keyed.setup()
    await web.TCPSite(keyed, "127.0.0.1", 8813).start()
    TOKEN = "ui-token-0123456789-abcd"
    locked = serve_ui(ui.make_app(base, autoscaler_url=base, api_key=fake_vast.KEY, access_token=TOKEN))
    await locked.setup()
    await web.TCPSite(locked, "127.0.0.1", 8814).start()
    # Behind a reverse proxy that serves it under a path and strips the prefix. The proxy also
    # sets a cookie and checks it comes back, as sign-in proxies do: the page's own requests must
    # carry it. No server key: callers bring theirs.
    behind = serve_ui(ui.make_app(base, autoscaler_url=base))
    await behind.setup()
    await web.TCPSite(behind, "127.0.0.1", 8815).start()

    async def sign_in_proxy(request):
        if request.match_info.get("tail") and request.cookies.get("session") != "signed-in":
            return web.Response(status=401, text="sign in first")  # as a sign-in proxy would
        dropped = {"host", "content-length", "cookie"}
        headers = {k: v for k, v in request.headers.items() if k.lower() not in dropped}
        async with aiohttp.ClientSession(auto_decompress=False) as s, s.request(
                request.method, f"http://127.0.0.1:8815/{request.match_info.get('tail', '')}", params=request.query,
                data=await request.read(), allow_redirects=False,
                headers={**headers, "Host": request.host}) as up:
            resp = web.StreamResponse(status=up.status, headers={
                k: v for k, v in up.headers.items() if k.lower() not in ("content-length", "transfer-encoding")})
            resp.set_cookie("session", "signed-in", path="/tools/ui")
            await resp.prepare(request)
            try:
                async for chunk in up.content.iter_any():
                    await resp.write(chunk)
            except (aiohttp.ClientConnectionResetError, ConnectionResetError):
                pass  # the page went away mid-stream (a worker view, say)
            return resp
    gate = web.Application()
    gate.router.add_route("*", "/tools/ui/{tail:.*}", sign_in_proxy)
    gate.router.add_route("*", "/tools/ui", sign_in_proxy)  # no trailing slash: tail is ''

    gate_runner = web.AppRunner(gate); await gate_runner.setup()
    await web.TCPSite(gate_runner, "127.0.0.1", 8816).start()

    problems = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(executable_path=CHROME)
        page = await browser.new_page(viewport={"width": 1400, "height": 1000})
        page.on("console", lambda m: m.type in ("error", "warning") and problems.append(f"console {m.type}: {m.text}"))
        page.on("pageerror", lambda e: problems.append(f"pageerror: {e}"))
        await page.goto("http://127.0.0.1:8812/")
        await page.fill("#key", fake_vast.KEY)
        await page.click("#connect")
        await page.click("#eps button")
        await page.wait_for_selector(".tabs button.on")
        await page.wait_for_selector("table.wk tbody tr")
        async def live():
            return "live" in await page.locator("details.workers > summary").inner_text()
        await until(live)
        state["instances_hidden"] = False  # a later lookup finds them; nothing is shown meanwhile
        print("workers:", (await page.locator("details.workers > summary").inner_text()).replace("\n", " "))
        print("worker rows:", await page.locator("table.wk tbody tr.worker").count(),
              "| statuses:", sorted(set(await page.locator("table.wk .st").all_inner_texts())))
        tabs = await page.locator(".tabs button").all_inner_texts()
        print("tabs:", tabs)
        print("badges:", await page.locator(".badges").inner_text())

        # Layout: the workers are in the sidebar, the key box folds once connected, and Send is
        # on screen without scrolling, even in a short window.
        assert await page.locator("aside.side details.workers table.wk").count() >= 1
        assert not await page.locator("#key-box").get_attribute("open")
        for height in (1000, 700):
            await page.set_viewport_size({"width": 1400, "height": height})
            box = await page.locator("button.go:text-is(\"Send\")").bounding_box()
            assert box["y"] + box["height"] <= height, (height, box)
        await page.set_viewport_size({"width": 1400, "height": 1000})
        print("layout ok")

        # Chat, streaming (default)
        await page.click("button.go:text-is(\"Send\")")
        await page.wait_for_selector(".result .meta .t")
        print("stream result:", (await page.locator(".result").first.inner_text()).replace("\n", " | ")[:200])
        print("transcript:", (await page.locator(".transcript").inner_text()).replace("\n", " | "))
        async def named():
            return "worker 1001" in await page.locator(".result").first.locator(".served-line").inner_text()
        await until(named)
        print("served:", await page.locator(".result").first.locator(".served-line").inner_text())
        await page.screenshot(path=f"{SHOTS}/chat-stream.png", full_page=True)

        # Chat, follow-up without streaming
        await page.locator(".editor input[type=checkbox]").first.uncheck()  # stream
        await page.locator(".editor textarea").nth(1).fill("And again?")
        await page.click("button.go:text-is(\"Send\")")
        async def second_done():
            return (await page.locator(".result").count() >= 2 and
                    "waiting" not in await page.locator(".result .meta").first.inner_text())
        await until(second_done)
        print("json result:", (await page.locator(".result").first.locator(".out").inner_text())[:120])
        print("messages sent:", (await page.locator("textarea.json").input_value()).count('"role"'))
        asked = (await page.locator(".result").first.locator("> .msg").inner_text()).lower()
        assert "conversation 1 · turn 2" in asked and "and again?" in asked, asked
        head = await page.locator(".convo-head").inner_text()
        assert "2 turns so far" in head, head
        asked_first = []
        page.once("dialog", lambda d: (asked_first.append(d.message), asyncio.ensure_future(d.accept())))
        await page.click("text=New conversation")
        assert asked_first and "2 turns" in asked_first[0], asked_first  # two turns would be lost
        head = await page.locator(".convo-head").inner_text()
        assert "Conversation 2 · new" in head and not await page.locator(".transcript").is_visible(), head
        print("conversation labels ok")
        await page.screenshot(path=f"{SHOTS}/chat-turns.png", full_page=True)

        # A reasoning model: thinking shown apart, only the answer joins the conversation
        state["reasoning"] = "some"
        await page.locator(".editor input[type=checkbox]").first.check()  # stream
        await page.locator(".editor textarea").nth(1).fill("Think first")
        await page.click("button.go:text-is(\"Send\")")
        card = page.locator(".result").first
        async def finished():
            return await card.locator(".meta .t").count() > 0
        await until(finished)
        assert await card.locator(".think-text").text_content() == "Let me think."
        assert await card.locator(".out").inner_text() == "Hello there"
        said = await page.locator(".transcript .msg.assistant").inner_text()
        assert "Hello there" in said and "think" not in said, said
        state["reasoning"] = "all"
        await page.locator(".editor textarea").nth(1).fill("Think only")
        await page.click("button.go:text-is(\"Send\")")
        await page.wait_for_selector(".result >> nth=0 >> .warn")
        assert "max_tokens" in await page.locator(".result").first.locator(".warn").inner_text()
        assert "1 turn so far" in await page.locator(".convo-head").inner_text()  # not advanced
        assert await page.locator(".editor textarea").nth(1).input_value() == "Think only"  # kept to retry
        state["reasoning"] = None
        print("reasoning ok")
        await page.screenshot(path=f"{SHOTS}/chat-reasoning.png", full_page=True)

        # Every control is named, for screen readers: by a label, or aria-label where none shows
        unnamed = await page.evaluate("""() => [...document.querySelectorAll(".ws input, .ws textarea, .ws select")]
            .filter(e => !e.labels?.length && !e.getAttribute("aria-label")).map(e => e.outerHTML.slice(0, 80))""")
        assert unnamed == [], unnamed
        # Fields added in the editor by hand survive the form rewriting the body, until reset
        editor = page.locator("textarea.json")
        body = json.loads(await editor.input_value())
        await editor.fill(json.dumps({**body, "top_p": 0.5}))
        await page.get_by_label("max_tokens", exact=True).fill("77")
        body = json.loads(await editor.input_value())
        assert body["top_p"] == 0.5 and body["max_tokens"] == 77, body
        assert "top_p" in await page.locator(".editor p.hint:has-text('kept')").inner_text()
        await page.click("text=reset from the form")
        assert "top_p" not in json.loads(await editor.input_value())
        # An empty turn is refused, not sent
        before = await page.locator(".result").count()
        await page.locator(".editor textarea").nth(1).fill("")
        await page.click("button.go:text-is(\"Send\")")
        assert "Write a message first" in await page.locator(".editor p.err").inner_text()
        assert await page.locator(".result").count() == before
        await page.locator(".editor textarea").nth(1).fill("Hello")
        # Leaving while a load run is going asks first; declining keeps it running
        await page.click("text=Load…")
        await page.click("button.go:text-is(\"Start load\")")
        await page.wait_for_selector("text=Stop load")
        asked = []
        async def decline(dialog):
            asked.append(dialog.message)
            await dialog.dismiss()
        page.once("dialog", decline)
        await page.click("#eps button")
        async def was_asked():
            return bool(asked)
        await until(was_asked)
        assert "load run" in asked[0] and await page.locator("text=Stop load").is_visible(), asked
        await page.click("text=Stop load")
        await page.click("text=Load…")  # closed again, as the load checks below expect
        print("labels, kept edits, empty turn and leave-confirm ok")

        # Streaming on, sent ×4: the burst goes without streaming and says so; the form keeps it
        await page.locator(".editor input[type=checkbox]").first.check()  # stream
        await page.select_option(".go-row select", "4")
        await page.click("button.go:text-is(\"Send\")")
        async def burst_done():
            return "4/4 ok of 4" in await page.locator(".result").first.locator(".meta").inner_text()
        await until(burst_done)
        meta = await page.locator(".result").first.locator(".meta").inner_text()
        assert "sent without streaming" in meta and "false" not in meta, meta
        assert '"stream": true' in await page.locator("textarea.json").input_value()
        assert not await page.locator(".editor p.err").is_visible()
        await page.select_option(".go-row select", "1")
        print("streaming burst ok")
        await page.click("text=Load…")
        await page.select_option(".loadbox select", "0")  # steady, one segment
        inputs = page.locator(".loadbox table.profile input")
        await inputs.nth(0).fill("4"); await inputs.nth(1).fill("4"); await inputs.nth(2).fill("1")
        await page.click("text=Start load")
        async def load_done():
            return "done" in await page.locator(".result").first.locator(".meta").inner_text()
        await until(load_done, timeout=30)
        meta = await page.locator(".result").first.locator(".meta").inner_text()
        assert "sent without streaming" in meta and "failed" not in meta, meta
        await page.click("text=Load…")  # close it again
        print("streaming load ok")

        # SDK view
        await page.click("text=Python SDK")
        sdk = await page.locator("pre:visible").first.inner_text()
        assert 'endpoint.request("/v1/chat/completions", payload, stream=True)' in sdk, sdk
        print("sdk view ok")
        await page.click(".ctabs >> text=JSON")

        # Show all routes, images, then a burst
        await page.check(".tabs input[type=checkbox]")
        await page.click(".tabs >> text=Images")
        await page.click("button.go:text-is(\"Send\")")
        await page.wait_for_selector(".result .imgs img", state="attached")
        print("image ok")
        await page.locator(".editor input[type=number]").first.fill("2")  # n=2 images per request
        await page.select_option(".go-row select", "4")
        await page.click("button.go:text-is(\"Send\")")
        async def four():
            return await page.locator(".result").first.locator(".burst-grid .cell").count() == 4
        await until(four)
        burst_images = await page.locator(".result").first.locator(".burst-grid img").count()
        print("burst images (n=2 ×4):", burst_images)
        assert burst_images == 8, burst_images
        cells = await page.locator(".result").first.locator(".burst-grid .cell .served").all_inner_texts()
        assert cells == ["1001"] * 4, cells
        print("burst:", (await page.locator(".result").first.locator(".meta").inner_text()).replace("\n", " "))
        await page.screenshot(path=f"{SHOTS}/images-burst.png", full_page=True)

        # Load run: 8/s for 3 s, then the charts, hover and per-second table
        await page.click("text=Load…")
        await page.select_option(".loadbox select", "0")  # steady preset, one segment
        inputs = page.locator(".loadbox table.profile input")
        await inputs.nth(0).fill("8"); await inputs.nth(1).fill("8"); await inputs.nth(2).fill("3")
        print("estimate:", await page.locator(".loadbox .estimate").inner_text())
        await page.click("text=Start load")
        async def load_done():
            return "done" in await page.locator(".result").first.locator(".meta").inner_text()
        await until(load_done, timeout=30)
        print("load:", (await page.locator(".result").first.locator(".meta").inner_text()).replace("\n", " "))
        # Screen readers hear the run change state, not each second's redraw
        spoken = await page.locator(".result .visually-hidden[role=status]").first.inner_text()
        assert "load run done: 24 sent" in spoken, spoken
        by_worker = (await page.locator(".result").first.locator("details", has_text="served by").inner_text())
        assert "served by 1 worker" in by_worker and "worker 1001" in by_worker, by_worker
        print("by worker:", by_worker.replace("\n", " | ")[:160])
        print("charts:", await page.locator(".result").first.locator("svg.chart").count(),
              "| lines:", await page.locator(".result").first.locator("svg.chart polyline").count())
        await page.locator(".result .charts").first.scroll_into_view_if_needed()
        box = await page.locator(".result .charts").first.bounding_box()
        await page.mouse.move(box["x"] + box["width"] * 0.4, box["y"] + 60)
        await page.wait_for_selector(".tip:not([hidden])")
        print("tooltip:", (await page.locator(".tip").first.inner_text()).replace("\n", " | ")[:160])
        await page.screenshot(path=f"{SHOTS}/load.png", full_page=True)
        await page.mouse.move(0, 0)

        # Speech (media), embeddings (worker error)
        await page.click(".tabs >> text=Speech")
        assert await page.locator(".formswitch button.on").inner_text() == "speech"  # not a music model
        assert "chosen for" not in await page.locator(".formswitch").inner_text()
        await page.click("button.go:text-is(\"Send\")")
        await page.wait_for_selector(".result audio", state="attached")
        print("audio ok")
        await page.click(".tabs >> text=Embeddings")
        await page.click("button.go:text-is(\"Send\")")
        await page.wait_for_selector(".result.bad .err")
        print("error card:", (await page.locator(".result.bad .err").first.inner_text())[:120])
        assert "worker 1001" in await page.locator(".result.bad .served-line").first.inner_text()

        # Uploads: the editor shows placeholders, the worker gets the files
        wav = fake_vast.WAV * 50
        png = bytes.fromhex("89504e470d0a1a0a") + b"fake png body"
        await page.click(".tabs >> text=Transcribe")
        await page.locator(".editor input[type=file]").set_input_files(
            files=[{"name": "speech.wav", "mimeType": "audio/wav", "buffer": wav}])
        async def placed():
            return "@file:" in await page.locator("textarea.json").input_value()
        await until(placed)
        body = await page.locator("textarea.json").input_value()
        assert '"filename": "speech.wav"' in body and len(body) < 600, body
        await page.click("text=Python SDK")
        sdk = await page.locator("pre:visible").first.inner_text()
        assert 'payload["file"] = data_uri("speech.wav")' in sdk, sdk
        await page.click("text=OpenAI client")
        oa = await page.locator("pre:visible").first.inner_text()
        assert 'client.audio.transcriptions.create(file=open("speech.wav", "rb"), **body)' in oa, oa
        await page.click(".ctabs >> text=JSON")
        await page.click("button.go:text-is(\"Send\")")
        async def heard():
            return f"heard speech.wav ({len(wav)} bytes)" in await page.locator(".result").first.inner_text()
        await until(heard)
        print("transcribe ok")

        await page.click(".tabs >> text=Image edits")
        await page.locator(".editor input[type=file]").first.set_input_files(files=[
            {"name": "a.png", "mimeType": "image/png", "buffer": png},
            {"name": "b.png", "mimeType": "image/png", "buffer": png + b"!!"}])
        await until(placed)
        await page.click("button.go:text-is(\"Send\")")
        await page.wait_for_selector(".result >> nth=0 >> .imgs img", state="attached")
        raw = await page.locator(".result").first.locator("details.raw pre").text_content()
        assert __import__("json").loads(raw)["response"]["edited"] == [21, 23], raw
        print("image edit ok")

        await page.click(".tabs >> text=Video")
        await page.locator(".editor input[type=file]").set_input_files(
            files=[{"name": "ref.png", "mimeType": "image/png", "buffer": png}])
        await until(placed)
        await page.click("button.go:text-is(\"Send\")")
        await page.wait_for_selector(".result >> nth=0 >> video", state="attached")
        print("video ok")

        # Chat with an image: a content part, kept for the next turn
        await page.click(".tabs >> text=Chat")
        await page.locator(".editor input[type=checkbox]").first.uncheck()  # stream
        await page.locator(".editor textarea").nth(1).fill("What is this?")
        await page.locator(".editor input[type=file]").set_input_files(
            files=[{"name": "cat.png", "mimeType": "image/png", "buffer": png}])
        await until(placed)
        await page.click("button.go:text-is(\"Send\")")
        async def seen():
            return "[image_url image/png 21 bytes]" in await page.locator(".result").first.inner_text()
        await until(seen)
        asked = await page.locator(".result").first.locator("> .msg").inner_text()
        assert "[image: cat.png]" in asked, asked
        assert await page.locator(".transcript img.thumb").count() == 1
        body = await page.locator("textarea.json").input_value()
        assert body.count("@file:") == 1 and "cat.png" in body  # the image goes again with the next turn
        print("chat image ok")
        await page.screenshot(path=f"{SHOTS}/chat-image.png")

        # Result views: embeddings, rerank, score, speech batch, audio generate
        state["embeddings_ok"] = True
        views = {}
        for tab, wait in (("Embeddings", "table.view"), ("Rerank", "table.view"), ("Score", "table.view"),
                          ("Speech batch", ".batch audio"), ("Audio generate", "audio")):
            await page.click(f".tabs >> text={tab}")
            await page.click("button.go:text-is(\"Send\")")
            await page.wait_for_selector(f".result >> nth=0 >> {wait}", state="attached")
            views[tab] = (await page.locator(".result").first.locator(".out").inner_text()).replace("\n", " | ")
        state["embeddings_ok"] = False
        assert "3 vectors of 8 dimensions" in views["Embeddings"] and "1.000" in views["Embeddings"], views
        assert "| 1\t1.0000\t3\t" in views["Rerank"], views["Rerank"]  # the best-scoring document ranks first
        assert "0.5000" in views["Score"] and "Forgot login" in views["Score"], views["Score"]
        assert "voice not found" in views["Speech batch"], views["Speech batch"]
        assert await page.locator(".result").nth(1).locator(".batch audio").count() == 2
        await page.click(".tabs >> text=Embeddings")
        await page.click("text=About embeddings")
        dialog = page.locator("dialog.help[open]")
        assert "cosine similarity" in await dialog.inner_text()
        await dialog.locator("text=Close").click()
        assert await page.locator("dialog.help[open]").count() == 0
        await page.click(".tabs >> text=Speech")
        await page.click(".formswitch >> text=music")
        assert await page.locator("text=About music from lyrics").count() == 1  # follows the switch
        await page.click(".formswitch >> text=speech")
        print("help ok")
        print("views:", " // ".join(f"{k}: {v[:70]}" for k, v in views.items()))
        top = await page.locator(".result").nth(4).bounding_box()
        bottom = await page.locator(".result").nth(0).bounding_box()
        await page.screenshot(path=f"{SHOTS}/views.png", full_page=True, clip={
            "x": top["x"], "y": bottom["y"], "width": top["width"], "height": top["y"] + top["height"] - bottom["y"]})

        # Smoke test: chat passes, embeddings fails (the fake answers 422)
        await page.click("text=Smoke test…")
        smoke = page.locator(".result.smoke").first
        assert "2 requests" in await smoke.locator(".meta").inner_text()
        await smoke.locator("text=Run").click()
        async def smoked():
            return "done" in await smoke.locator(".meta").inner_text()
        await until(smoked)
        rows = await smoke.locator("tbody tr").all_inner_texts()
        assert "1/2 passed" in await smoke.locator(".meta").inner_text(), rows
        chat, embed = rows
        assert "pass" in chat and "1001" in chat and "embeddings" not in chat.lower(), chat
        assert "fail" in embed and "422" in embed, embed
        assert await smoke.locator("text=Run again").is_enabled()
        print("smoke:", " / ".join(r.replace("\t", " | ") for r in rows)[:240])
        await page.screenshot(path=f"{SHOTS}/smoke.png", full_page=True)

        # A server started with a key: the page connects by itself, and the OpenAI client
        # code it shows runs against this server's proxy.
        own = await browser.new_page(viewport={"width": 1400, "height": 1000})
        own.on("pageerror", lambda e: problems.append(f"pageerror (keyed): {e}"))
        await own.goto("http://127.0.0.1:8813/")
        await own.wait_for_selector("#eps button")
        assert await own.locator("#key-pill").inner_text() == "server's key"
        await own.click("#eps button")
        await own.wait_for_selector(".tabs button.on")
        await own.click("text=OpenAI client")
        code = await own.locator("pre:visible").first.inner_text()
        assert 'base_url="http://127.0.0.1:8813/e/flux-demo/v1"' in code and "client.chat.completions.create(**body)" in code
        proc = await asyncio.create_subprocess_exec(sys.executable, "-c", code,
                                                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        out, err = await asyncio.wait_for(proc.communicate(), 60)
        assert proc.returncode == 0 and "Hello" in out.decode(), err.decode()[-800:]
        print("openai client code ran:", out.decode().count("ChatCompletionChunk"), "chunks")
        async def counted():
            return (await own.locator("#traffic-count").inner_text()).strip() == "1"
        await until(counted)  # the left column counts proxied requests wherever you are
        await own.click("#traffic-nav")
        traffic = own.locator("table.traffic-table")
        async def shown():
            return await traffic.count() and "done" in await traffic.inner_text()
        await until(shown)
        row = await traffic.locator("tbody tr").first.inner_text()
        assert "flux-demo" in row and "1001" in row and "Hello there" in row and "Explain what a serverless" in row, row
        await own.screenshot(path=f"{SHOTS}/traffic.png", full_page=True)
        await own.click(".eps button[data-name=flux-demo]")  # and back to the endpoint
        await own.wait_for_selector("details.workers")

        # Smoke test of upload routes, with the files it generates
        state["templates"][0]["env"] = state["templates"][0]["env"].replace(
            "OPENAI_ROUTES=/v1/chat/completions,/v1/embeddings",
            "OPENAI_ROUTES=/v1/chat/completions,/v1/audio/transcriptions,/v1/images/edits")
        await own.click("#eps button[data-name=flux-demo]")  # read the endpoint again
        await own.wait_for_selector(".tabs >> text=Transcribe")
        await own.click("text=Smoke test…")
        smoke = own.locator(".result.smoke").first
        await smoke.locator("text=Run").click()
        async def smoked():
            return "done" in await smoke.locator(".meta").inner_text()
        await until(smoked)
        rows = await smoke.locator("tbody tr").all_inner_texts()
        assert "3/3 passed" in await smoke.locator(".meta").inner_text(), rows
        assert "heard smoke.wav (16044 bytes)" in rows[1] and "1 image(s)" in rows[2], rows
        # A music model on the speech route gets the music form, and a short smoke song
        state["templates"][0]["env"] = state["templates"][0]["env"].replace(
            "VLLM_MODEL=Qwen/Qwen3-8B", "VLLM_MODEL=m-a-p/YuE2-3B").replace(
            "/v1/images/edits", "/v1/images/edits,/v1/audio/speech")
        await own.click("#eps button[data-name=flux-demo]")
        await own.wait_for_selector(".tabs >> text=Speech")
        await own.click(".tabs >> text=Speech")
        await own.wait_for_selector("text=lyrics ([verse], [chorus] … sections)")
        body = __import__("json").loads(await own.locator("textarea.json").input_value())
        assert body["model"] == "m-a-p/YuE2-3B" and body["max_new_tokens"] == 500, body
        assert body["instructions"] and "[chorus]" in body["input"] and body["extra_params"] == {"cot": "off"}, body
        switch = own.locator(".formswitch")
        assert "chosen for m-a-p/YuE2-3B" in await switch.inner_text()
        assert await switch.locator("button.on").inner_text() == "music"
        await switch.locator("text=speech").click()  # the same route as text to speech
        body = __import__("json").loads(await own.locator("textarea.json").input_value())
        assert "max_new_tokens" not in body and body["input"].startswith("A quick update"), body
        await switch.locator("text=music").click()
        body = __import__("json").loads(await own.locator("textarea.json").input_value())
        assert body["max_new_tokens"] == 500, body
        await own.click("button.go:text-is(\"Send\")")
        await own.wait_for_selector(".result >> nth=0 >> audio", state="attached")
        await own.click("text=Smoke test…")
        sent = await own.locator(".result.smoke").first.locator("details.raw pre").text_content()
        assert '"max_new_tokens": 125' in sent, sent
        print("music form ok")
        # ComfyUI: how to get the endpoint's workflows from a worker, then one dropped in
        import json as _json
        state["endpoints"] = [7, 9]
        await own.goto("http://127.0.0.1:8813/")
        await own.click("#eps button[data-name=comfy-demo]")
        await own.wait_for_selector(".tabs button.on >> text=Workflow")
        assert "workflows: 1 provisioned" in await own.locator(".badges").inner_text()
        assert await own.locator("text=show all routes").count() == 0
        howto = own.locator("details.howto")
        async def worker_named():
            return "C.1001:/opt/comfyui-api-wrapper/workflows/" in await howto.inner_text()
        await until(worker_named)  # the commands name a live worker once the panel has one
        await own.locator(".editor").first.screenshot(path=f"{SHOTS}/comfy-howto.png")
        text = await howto.inner_text()
        assert "image_z_image.json (the benchmark's)" in text, text
        assert "1000" not in text  # the loading worker may not have the files yet
        assert "ssh $(vastai ssh-url 1001) cat /opt/comfyui-api-wrapper/workflows/image_z_image.json > image_z_image.json" in text, text
        # Nothing to smoke-test until a workflow is loaded
        await own.click("text=Smoke test…")
        smoke = own.locator(".result.smoke").first
        assert "load a workflow in the Workflow tab first" in await smoke.inner_text()
        assert await smoke.locator("button.go:text-is(\"Run\")").is_disabled()
        picker = own.locator(".editor input[type=file]")
        async def editor_says(words):
            async def check():
                return words in await own.locator(".editor").inner_text()
            await until(check)
        gui = _json.dumps({"nodes": [], "links": []}).encode()
        await picker.set_input_files(files=[{"name": "gui.json", "mimeType": "application/json", "buffer": gui}])
        await editor_says("GUI format")
        envelope = _json.dumps({"input": {"workflow_json": fake_vast.Z_IMAGE}}).encode()  # as in payloads/
        await picker.set_input_files(files=[{"name": "payload.json", "mimeType": "application/json", "buffer": envelope}])
        await editor_says(f"{len(fake_vast.Z_IMAGE)} nodes, from payload.json")
        flat = _json.dumps(fake_vast.Z_IMAGE).encode()
        await picker.set_input_files(files=[{"name": "image_z_image.json", "mimeType": "application/json", "buffer": flat}])
        await editor_says(f"{len(fake_vast.Z_IMAGE)} nodes, from image_z_image.json")
        assert not await howto.get_attribute("open") and await howto.count() == 1  # folded away once loaded
        early = own.locator(".result.smoke").last  # opened before any workflow: now it can run
        assert "runs the workflow loaded" in await early.inner_text()
        assert not await early.locator("button.go:text-is(\"Run\")").is_disabled()
        fields = own.locator(".comfy-fields")
        assert await fields.locator("textarea").nth(0).input_value() == "a lighthouse at dusk"  # positive first
        assert await fields.locator("textarea").nth(1).input_value() == "blurry"
        assert "negative prompt" in await fields.inner_text() and "node 6 · CLIPTextEncode" in await fields.inner_text()
        assert await fields.locator("input[type=text]").input_value() == "fighter_jet.png"
        assert await fields.locator("input[type=checkbox]").is_checked()  # seed: random each request
        await fields.locator("textarea").nth(0).fill("a red kite over the sea")
        body = _json.loads(await own.locator("textarea.json").input_value())
        assert body["input"]["workflow_json"]["6"]["inputs"]["text"] == "a red kite over the sea"
        assert body["input"]["return_outputs_as_base64"] is True and body["input"]["workflow_json"]["3"]["inputs"]["seed"] == "__RANDOM_INT__"
        await fields.locator("input[type=checkbox]").uncheck()
        body = _json.loads(await own.locator("textarea.json").input_value())
        assert body["input"]["workflow_json"]["3"]["inputs"]["seed"] == 42
        await own.click("button.go:text-is(\"Send\")")
        await own.wait_for_selector(".result >> nth=0 >> .comfy-out img", state="attached")
        out = await own.locator(".result").first.inner_text()
        assert "z-image_00001_.png" in out and "total 1.40s" in out and "1001" in out, out
        await own.click("text=HTTP via proxy")
        assert "/e/comfy-demo/generate/sync" in await own.locator("pre:visible").first.inner_text()
        await own.click(".ctabs >> text=JSON")
        await own.click("text=About comfyui workflows")
        assert "/opt/comfyui-api-wrapper/workflows/" in await own.locator("dialog.help[open]").inner_text()
        await own.locator("dialog.help[open] >> text=Close").click()
        # Now the smoke test runs the loaded workflow
        await own.click("text=Smoke test…")
        smoke = own.locator(".result.smoke").first
        await smoke.locator("button.go:text-is(\"Run\")").click()
        async def comfy_smoked():
            return "done" in await smoke.locator(".meta").inner_text()
        await until(comfy_smoked)
        assert "1/1 passed" in await smoke.locator(".meta").inner_text(), await smoke.inner_text()
        await own.screenshot(path=f"{SHOTS}/comfy.png", full_page=True)
        print("comfy ok")
        print("upload smoke:", " / ".join(r.replace("\t", " | ").replace("\n", " ") for r in rows)[:260])
        print("traffic row:", " | ".join(row.split("\t"))[:200])
        await own.screenshot(path=f"{SHOTS}/openai-view.png", full_page=True)
        await own.close()

        # Results stay with their endpoint: away to proxy traffic and back finds them
        n = await page.locator(".results > .result").count()
        await page.click("#traffic-nav")
        await page.click("#eps button")
        await page.wait_for_selector(".tabs button.on")
        assert await page.locator(".results > .result").count() == n > 0
        # No button is named only by a symbol
        bare = await page.evaluate("""() => [...document.querySelectorAll("button")]
            .filter(b => /^[×✕x]?$/.test(b.textContent.trim()) && !b.getAttribute("aria-label")).length""")
        assert bare == 0, bare
        # Removing results: one with its ×, then all
        assert f"{n} results" in await page.locator(".results-bar").inner_text()
        await page.locator(".results > .result").first.locator("> .close").click()
        assert await page.locator(".results > .result").count() == n - 1
        page.once("dialog", lambda d: asyncio.ensure_future(d.accept()))  # load runs are among them
        await page.click(".results-bar >> text=Clear all")
        assert await page.locator(".results > .result").count() == 0
        assert not await page.locator(".results-bar").is_visible()
        # The sidebar, workers included, stays in view while the page scrolls
        await page.mouse.wheel(0, 5000)
        box = await page.locator("details.workers > summary").bounding_box()
        assert 0 <= box["y"] < 1000, box
        print("clearing and sidebar ok")

        # Dropping files on a picker. Building a DataTransfer needs script, which the page's CSP
        # forbids to everything else, so this one context bypasses it.
        ctx = await browser.new_context(bypass_csp=True, viewport={"width": 1400, "height": 1000})
        drop_page = await ctx.new_page()
        drop_page.on("pageerror", lambda e: problems.append(f"pageerror (drop): {e}"))
        await drop_page.goto("http://127.0.0.1:8813/")
        await drop_page.click("#eps button")
        await drop_page.wait_for_selector(".tabs >> text=Chat")
        await drop_page.click(".tabs >> text=Chat")
        async def drop(names_types):
            data = await drop_page.evaluate_handle("""(files) => {
                const dt = new DataTransfer();
                for (const [name, type] of files) dt.items.add(new File(["x".repeat(2048)], name, { type }));
                return dt; }""", names_types)
            zone = drop_page.locator(".drop").first
            await zone.dispatch_event("dragover", {"dataTransfer": data})
            await zone.dispatch_event("drop", {"dataTransfer": data})
        await drop([["cat.png", "image/png"], ["notes.txt", "text/plain"]])
        async def chipped():
            return await drop_page.locator(".chip").count() == 1
        await until(chipped)
        assert "cat.png · 2 KB" in await drop_page.locator(".chip").inner_text()
        assert "notes.txt (wrong type)" in await drop_page.locator(".drop-note").inner_text()
        await drop([["dog.png", "image/png"]])  # several allowed: it adds
        async def two():
            return await drop_page.locator(".chip").count() == 2
        await until(two)
        assert (await drop_page.locator("textarea.json").input_value()).count("@file:") == 2
        await drop_page.locator(".chip").first.locator("button").click()  # remove cat.png
        assert await drop_page.locator(".chip").count() == 1
        body = await drop_page.locator("textarea.json").input_value()
        assert body.count("@file:") == 1 and "dog.png" in body and "cat.png" not in body, body
        await drop_page.locator(".drop").first.screenshot(path=f"{SHOTS}/drop.png")
        await ctx.close()
        print("drop ok")

        # A shared server asks for its access token before anything else, and its code
        # samples read the token from the environment rather than carrying it
        shared = await browser.new_page(viewport={"width": 1400, "height": 1000})
        shared.on("pageerror", lambda e: problems.append(f"pageerror (token): {e}"))
        await shared.goto("http://127.0.0.1:8814/")
        await shared.wait_for_selector("#token-field:not([hidden])")
        assert not await shared.locator("#key").is_visible()  # the token alone, until it works
        assert await shared.locator("#eps button").count() == 0  # nothing until the token
        await shared.click("#connect")
        assert "access token" in await shared.locator("#error").inner_text()
        await shared.fill("#token", "wrong-token-0123456789")
        await shared.click("#connect")
        await shared.wait_for_selector("#error:has-text('needs its access token')")
        assert await shared.locator("#token").is_visible() and not await shared.locator("#key").is_visible()
        await shared.fill("#token", TOKEN)
        await shared.click("#connect")
        await shared.wait_for_selector("#eps button")
        assert not await shared.locator("#token-field").is_visible()
        # Remembered: a reload opens straight away
        await shared.reload()
        await shared.wait_for_selector("#eps button")
        assert not await shared.locator("#token-field").is_visible()
        await shared.click("#eps button")
        await shared.wait_for_selector(".tabs button.on")
        await shared.click(".ctabs button:text-is('OpenAI client')")
        code = await shared.locator(".editor pre").first.inner_text()
        assert 'api_key=os.environ["SERVERLESS_UI_TOKEN"]' in code and TOKEN not in code, code
        await shared.click(".ctabs button:text-is('JSON')")
        await shared.click("button.go:text-is(\"Send\")")
        await shared.wait_for_selector(".result .meta .t")
        shared_html = await shared.content()
        assert TOKEN not in shared_html and fake_vast.KEY not in shared_html
        await shared.click("#eps button:has-text('comfy-demo')")
        await shared.wait_for_selector(".tabs button.on:text-is('Workflow')")
        await shared.click(".ctabs button:text-is('HTTP via proxy')")
        code = await shared.locator(".code-head ~ pre").inner_text()
        assert 'headers={"Authorization": f"Bearer {os.environ[\'SERVERLESS_UI_TOKEN\']}"}' in code and "import os" in code, code
        assert TOKEN not in code
        print("comfy proxy code with token:", code.splitlines()[3])
        stored = await shared.evaluate("() => [Object.values(localStorage), sessionStorage.length, document.cookie]")
        assert stored == [[TOKEN], 0, ""], stored  # the token, and never the key
        await shared.click("#key-box > summary")
        await shared.click("#forget-token")
        await shared.wait_for_selector("#token-field:not([hidden])")
        assert await shared.evaluate("() => localStorage.length") == 0
        assert await shared.locator("#eps button").count() == 0
        await shared.close()
        # The link the server prints carries the token in its fragment: it opens connected,
        # and the token leaves the address bar
        linked = await browser.new_page(viewport={"width": 1400, "height": 1000})
        linked.on("pageerror", lambda e: problems.append(f"pageerror (link): {e}"))
        await linked.goto(f"http://127.0.0.1:8814/#token={TOKEN}")
        await linked.wait_for_selector("#eps button")
        assert "token" not in linked.url and not await linked.locator("#token-field").is_visible(), linked.url
        await linked.close()
        print("access token ok")

        # Under a path, behind a proxy that wants its cookie back, opened without the trailing
        # slash, with the caller's own key
        under = await browser.new_page(viewport={"width": 1400, "height": 1000})
        under.on("pageerror", lambda e: problems.append(f"pageerror (behind proxy): {e}"))
        await under.goto("http://127.0.0.1:8816/tools/ui")
        assert not await under.locator("#token-field").is_visible()  # localhost, no key: no token
        await under.fill("#key", fake_vast.KEY)
        await under.click("#connect")
        await under.click("#eps button")
        await under.wait_for_selector(".tabs button.on")
        await under.click("button.go:text-is(\"Send\")")
        await under.wait_for_selector(".result .meta .t")
        await under.click(".ctabs button:text-is('OpenAI client')")
        code = await under.locator(".code-head ~ pre").inner_text()
        assert 'base_url="http://127.0.0.1:8816/tools/ui/e/flux-demo/v1"' in code, code
        assert 'api_key=os.environ["VAST_API_KEY"]' in code, code
        await under.close()
        print("behind a proxy, under a path ok")

        html = await page.content()
        stored = await page.evaluate("() => [localStorage.length, sessionStorage.length, document.cookie]")
        print("key in DOM:", fake_vast.KEY in html, "| storage:", stored)
        if fake_vast.KEY in html:
            problems.append("the key is in the page's DOM")
        if stored != [0, 0, ""]:
            problems.append(f"the page stored something: {stored}")
        await page.screenshot(path=f"{SHOTS}/final.png", full_page=True)
        await browser.close()
    print("screenshots:", SHOTS)
    print("problems:", problems or "none")
    if problems:
        sys.exit(1)

asyncio.run(main())
