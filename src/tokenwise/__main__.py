"""CLI entry point: tokenwise count|cost|optimize <text>."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from tokenwise.core import CostEstimator, TokenCounter, TokenOptimizer

app = typer.Typer(help="TokenWise — Token usage optimization toolkit for LLM applications.")
console = Console()


@app.command()
def count(
    text: str = typer.Argument(..., help="Text to count tokens for"),
    model: str = typer.Option("gpt-4", "--model", "-m", help="Model name"),
) -> None:
    """Count tokens in the given text."""
    counter = TokenCounter()
    tokens = counter.count(text, model)
    console.print(f"[bold green]Model:[/] {model}")
    console.print(f"[bold green]Tokens:[/] {tokens}")
    console.print(f"[bold green]Characters:[/] {len(text)}")
    console.print(f"[bold green]Words:[/] {len(text.split())}")


@app.command()
def cost(
    text: str = typer.Argument(..., help="Text to estimate cost for"),
    model: str = typer.Option("gpt-4", "--model", "-m", help="Model name"),
    direction: str = typer.Option("input", "--direction", "-d", help="input or output"),
    compare: bool = typer.Option(False, "--compare", "-c", help="Compare across all models"),
) -> None:
    """Estimate API cost for the given text."""
    estimator = CostEstimator()
    if compare:
        results = estimator.compare_models(text, direction=direction)
        table = Table(title="Cost Comparison")
        table.add_column("Model", style="cyan")
        table.add_column("Tokens", justify="right")
        table.add_column("Cost (USD)", justify="right", style="green")
        table.add_column("Context Window", justify="right")
        for m, info in results.items():
            table.add_row(
                m,
                str(info["tokens"]),
                f"${info['cost']:.8f}",
                str(info["context_window"]),
            )
        console.print(table)
    else:
        counter = TokenCounter()
        tokens = counter.count(text, model)
        est = estimator.estimate(tokens, model, direction)
        console.print(f"[bold green]Model:[/] {model}")
        console.print(f"[bold green]Tokens:[/] {tokens}")
        console.print(f"[bold green]Direction:[/] {direction}")
        console.print(f"[bold green]Estimated cost:[/] ${est:.8f}")


@app.command()
def optimize(
    text: str = typer.Argument(..., help="Text to optimize"),
    model: str = typer.Option("gpt-4", "--model", "-m", help="Model name"),
) -> None:
    """Optimize text to reduce token count."""
    optimizer = TokenOptimizer()
    report = optimizer.savings_report(text, model)
    console.print(f"[bold green]Original tokens:[/] {report['original_tokens']}")
    console.print(f"[bold green]Optimized tokens:[/] {report['optimized_tokens']}")
    console.print(
        f"[bold green]Tokens saved:[/] {report['tokens_saved']} ({report['savings_pct']}%)"
    )
    console.print(f"\n[bold]Optimized text:[/]\n{report['optimized_text']}")


if __name__ == "__main__":
    app()
