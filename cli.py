"""Command-line entrypoint for the Deep Research Agent.

Useful for quick demos and debugging without spinning up the web server.
Handles the human-in-the-loop interrupt via a terminal prompt.
"""

import uuid

import typer
from langgraph.types import Command

from src.graph import get_graph, initial_state
from src.logging_config import get_logger

app = typer.Typer(add_completion=False)
logger = get_logger(__name__)


@app.command()
def research(
    query: str = typer.Argument(..., help="The research question to investigate."),
    hitl: bool = typer.Option(True, help="Require human approval of the research plan."),
) -> None:
    """Run a full research job end-to-end from the terminal."""
    graph = get_graph()
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    typer.secho(f"Case file #{thread_id[:8]} — starting research...", fg=typer.colors.YELLOW)
    result = graph.invoke(initial_state(query, hitl), config=config)

    while graph.get_state(config).next:
        snapshot = graph.get_state(config)
        interrupt_payload = None
        for task in snapshot.tasks:
            if task.interrupts:
                interrupt_payload = task.interrupts[0].value
                break

        if interrupt_payload is None:
            typer.secho("Graph paused without an interrupt payload; aborting.", fg=typer.colors.RED)
            raise typer.Exit(1)

        typer.secho("\nProposed research plan:", fg=typer.colors.CYAN, bold=True)
        for i, sq in enumerate(interrupt_payload["sub_questions"], start=1):
            typer.echo(f"  {i}. {sq['question']}")
            typer.echo(f"     ({sq['rationale']})")

        approved = typer.confirm("\nApprove this plan?", default=True)
        feedback = ""
        if not approved:
            feedback = typer.prompt("Feedback for refining the plan", default="")

        result = graph.invoke(Command(resume={"approved": approved, "feedback": feedback}), config=config)

    report = result.get("final_report")
    if report is None:
        typer.secho("Research finished without a report.", fg=typer.colors.RED)
        raise typer.Exit(1)

    typer.secho(f"\n{'=' * 70}", fg=typer.colors.YELLOW)
    typer.secho(report.title, fg=typer.colors.GREEN, bold=True)
    typer.secho(f"{'=' * 70}\n", fg=typer.colors.YELLOW)
    typer.echo(report.executive_summary + "\n")

    for section in report.sections:
        typer.secho(section.heading, bold=True)
        typer.echo(section.body + "\n")

    typer.secho("Citations:", bold=True)
    for c in report.citations:
        typer.echo(f"  - {c.claim} ({c.source_url})")

    if report.open_questions:
        typer.secho("\nOpen questions:", bold=True, fg=typer.colors.RED)
        for q in report.open_questions:
            typer.echo(f"  - {q}")


if __name__ == "__main__":
    app()
