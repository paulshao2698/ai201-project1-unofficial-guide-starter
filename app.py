import gradio as gr

from query import ask


def handle_query(question: str):
    if not question or not question.strip():
        return "Please enter a question.", ""

    result = ask(question.strip())

    answer = result["answer"]
    sources = "\n\n".join(f"• {source}" for source in result["sources"])

    return answer, sources


with gr.Blocks(title="DMV Weekend Guide") as demo:
    gr.Markdown("# DMV Weekend Guide")
    gr.Markdown(
        "Ask about student-friendly weekend activities in DC, Northern Virginia, and Maryland. "
        "Answers are based only on the documents loaded into the local vector store."
    )

    question = gr.Textbox(
        label="Your question",
        placeholder="Example: Is Burke Lake good for beginner boating?",
        lines=2,
    )

    ask_button = gr.Button("Ask")

    answer = gr.Textbox(label="Answer", lines=8)
    sources = gr.Textbox(label="Retrieved from", lines=8)

    ask_button.click(
        handle_query,
        inputs=question,
        outputs=[answer, sources],
        queue=False,
    )

    question.submit(
        handle_query,
        inputs=question,
        outputs=[answer, sources],
        queue=False,
    )


if __name__ == "__main__":
    demo.launch()