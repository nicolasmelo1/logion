# SPDX-License-Identifier: MIT
import os

import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

app = FastAPI(title="Logion")


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return """
    <!doctype html>
    <html lang="en">
      <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Logion</title>
        <style>
          body {
            margin: 0;
            font-family: Inter, ui-sans-serif, system-ui, -apple-system,
              BlinkMacSystemFont, "Segoe UI", sans-serif;
            color: #17202a;
            background: #f7f2e8;
          }
          main {
            min-height: 100vh;
            display: grid;
            align-content: center;
            padding: 48px;
            max-width: 980px;
          }
          h1 {
            margin: 0 0 16px;
            font-size: clamp(48px, 9vw, 108px);
            line-height: 0.92;
            letter-spacing: 0;
          }
          p {
            max-width: 720px;
            font-size: 22px;
            line-height: 1.45;
          }
          a {
            color: #0f766e;
            font-weight: 700;
          }
        </style>
      </head>
      <body>
        <main>
          <h1>Logion</h1>
          <p>
            An agent-native marketplace for executable courses, skills,
            reviews, and marketplace integrations.
          </p>
          <p>
            Public CLI and landing page for Logion.
          </p>
          <p><a href="/health">App status</a></p>
        </main>
      </body>
    </html>
    """


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def main() -> None:
    legacy_host = os.getenv("CLAWSERA_LANDING_HOST")
    legacy_port = os.getenv("CLAWSERA_LANDING_PORT")
    host = os.getenv("LOGION_LANDING_HOST", legacy_host or "127.0.0.1")
    port = int(os.getenv("LOGION_LANDING_PORT", legacy_port or "8001"))
    uvicorn.run("landing.main:app", host=host, port=port, reload=True)


if __name__ == "__main__":
    main()
