import httpx
import typer

app = typer.Typer(help="Logion CLI for AI agents.")


@app.command()
def health(api_url: str = "http://localhost:8000") -> None:
    response = httpx.get(f"{api_url}/health", timeout=10)
    response.raise_for_status()
    typer.echo(response.json())


if __name__ == "__main__":
    app()
