"""
Answer Generator Module
Generates RFP answers using similar documents and optional LLM enhancement
"""

import re
from typing import List, Dict, Optional
from dataclasses import dataclass

from .vector_store import VectorStore, SearchResult
from .config import settings


@dataclass
class GeneratedAnswer:
    """Represents a generated answer with metadata"""
    question: str
    answer: str
    confidence_score: float
    sources: List[Dict]
    method: str  # 'template', 'similarity', 'llm'


class AnswerGenerator:
    """Generates answers to RFP questions using past documents"""

    def __init__(self, vector_store: VectorStore):
        self.vector_store = vector_store
        self.llm_client = None

    def _initialize_llm(self):
        """Initialize LLM client if configured"""
        if self.llm_client is not None:
            return

        if not settings.USE_LLM:
            return

        if settings.LLM_PROVIDER == "openai" and settings.OPENAI_API_KEY:
            try:
                from openai import OpenAI
                self.llm_client = OpenAI(api_key=settings.OPENAI_API_KEY)
            except ImportError:
                print("OpenAI package not installed")

        elif settings.LLM_PROVIDER == "anthropic" and settings.ANTHROPIC_API_KEY:
            try:
                import anthropic
                self.llm_client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
            except ImportError:
                print("Anthropic package not installed")

    def generate_answer(
        self,
        question: str,
        use_llm: bool = None,
        top_k: int = None
    ) -> GeneratedAnswer:
        """Generate an answer for a single RFP question"""

        if use_llm is None:
            use_llm = settings.USE_LLM

        if top_k is None:
            top_k = settings.TOP_K_RESULTS

        # Search for similar content
        search_results = self.vector_store.search_similar(
            query=question,
            top_k=top_k,
            include_answers=True
        )

        if not search_results:
            return GeneratedAnswer(
                question=question,
                answer="No similar documents found in the knowledge base. Please add more RFP-answer pairs for better results.",
                confidence_score=0.0,
                sources=[],
                method="none"
            )

        # Collect relevant answers and context
        relevant_answers = []
        sources = []

        for result in search_results:
            sources.append({
                "file": result.source_file,
                "type": result.document_type,
                "similarity": round(result.similarity_score, 3),
                "excerpt": result.content[:200] + "..." if len(result.content) > 200 else result.content
            })

            if result.answer_content:
                relevant_answers.append({
                    "answer": result.answer_content,
                    "similarity": result.similarity_score,
                    "source": result.source_file
                })

        # Calculate confidence based on similarity scores
        avg_similarity = sum(r.similarity_score for r in search_results) / len(search_results)
        confidence = min(avg_similarity * 1.5, 1.0)  # Scale up but cap at 1.0

        # Generate answer
        if use_llm and self.llm_client:
            answer = self._generate_with_llm(question, search_results, relevant_answers)
            method = "llm"
        else:
            answer = self._generate_from_templates(question, search_results, relevant_answers)
            method = "similarity" if relevant_answers else "template"

        return GeneratedAnswer(
            question=question,
            answer=answer,
            confidence_score=confidence,
            sources=sources,
            method=method
        )

    def _generate_from_templates(
        self,
        question: str,
        search_results: List[SearchResult],
        relevant_answers: List[Dict]
    ) -> str:
        """Generate answer using similarity-based template matching"""

        if relevant_answers:
            # Sort by similarity and use the best matching answer as base
            relevant_answers.sort(key=lambda x: x['similarity'], reverse=True)

            answer_parts = []
            answer_parts.append("Based on similar previous RFP responses:\n")

            for i, ans in enumerate(relevant_answers[:3], 1):
                # Clean and format the answer
                cleaned_answer = self._clean_answer(ans['answer'])
                answer_parts.append(f"\n**Reference {i}** (from {ans['source']}, {ans['similarity']:.0%} match):\n")
                answer_parts.append(cleaned_answer)

            if len(relevant_answers) > 1:
                answer_parts.append("\n\n---\n**Synthesized Response:**\n")
                answer_parts.append(self._synthesize_answers(question, relevant_answers))

            return "\n".join(answer_parts)

        else:
            # No direct answers found, provide context-based response
            context_parts = []
            context_parts.append("No direct answer matches found, but here's relevant context:\n")

            for result in search_results[:3]:
                context_parts.append(f"\n**From {result.source_file}** ({result.similarity_score:.0%} relevant):\n")
                context_parts.append(f"> {result.content[:500]}...")

            context_parts.append("\n\n*Consider reviewing these documents to craft a tailored response.*")

            return "\n".join(context_parts)

    def _generate_with_llm(
        self,
        question: str,
        search_results: List[SearchResult],
        relevant_answers: List[Dict]
    ) -> str:
        """Generate answer using LLM with retrieved context"""

        self._initialize_llm()

        if not self.llm_client:
            return self._generate_from_templates(question, search_results, relevant_answers)

        # Build context from search results
        context_parts = []

        for result in search_results:
            context_parts.append(f"[Source: {result.source_file}]\n{result.content}")
            if result.answer_content:
                context_parts.append(f"[Previous Answer for similar question]\n{result.answer_content}")

        context = "\n\n---\n\n".join(context_parts)

        prompt = f"""You are an expert RFP response writer. Generate a professional, comprehensive answer to the following RFP question using the provided context from previous successful RFP responses.

RFP Question:
{question}

Context from previous RFP responses:
{context}

Instructions:
1. Write a clear, professional response that directly addresses the question
2. Use specific details and examples from the context where relevant
3. Maintain a confident but not boastful tone
4. Structure the answer logically with clear paragraphs
5. If the context doesn't fully address the question, note what additional information might be needed

Generated Answer:"""

        try:
            if settings.LLM_PROVIDER == "openai":
                response = self.llm_client.chat.completions.create(
                    model="gpt-4-turbo-preview",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=1500,
                    temperature=0.7
                )
                return response.choices[0].message.content

            elif settings.LLM_PROVIDER == "anthropic":
                response = self.llm_client.messages.create(
                    model="claude-3-sonnet-20240229",
                    max_tokens=1500,
                    messages=[{"role": "user", "content": prompt}]
                )
                return response.content[0].text

        except Exception as e:
            print(f"LLM generation error: {e}")
            return self._generate_from_templates(question, search_results, relevant_answers)

        return self._generate_from_templates(question, search_results, relevant_answers)

    def _clean_answer(self, answer: str) -> str:
        """Clean and format an answer"""
        # Remove excessive whitespace
        answer = re.sub(r'\s+', ' ', answer)
        # Break into paragraphs
        answer = re.sub(r'\. (?=[A-Z])', '.\n\n', answer)
        return answer.strip()

    def _synthesize_answers(self, question: str, answers: List[Dict]) -> str:
        """Synthesize multiple answers into a coherent response"""
        if not answers:
            return ""

        # Extract key phrases and common themes
        all_text = " ".join([a['answer'] for a in answers])

        # Simple extraction of key sentences
        sentences = re.split(r'[.!?]+', all_text)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 30]

        # Take diverse sentences
        if len(sentences) > 5:
            selected = sentences[:2] + sentences[len(sentences)//2:len(sentences)//2+2] + sentences[-1:]
        else:
            selected = sentences

        return " ".join(selected) + "."

    def generate_full_rfp_response(
        self,
        questions: List[str],
        use_llm: bool = None
    ) -> List[GeneratedAnswer]:
        """Generate answers for a list of RFP questions"""

        answers = []
        for question in questions:
            answer = self.generate_answer(question, use_llm=use_llm)
            answers.append(answer)

        return answers

    def export_response(
        self,
        answers: List[GeneratedAnswer],
        format: str = "markdown"
    ) -> str:
        """Export generated answers in the specified format"""

        if format == "markdown":
            return self._export_markdown(answers)
        elif format == "json":
            import json
            return json.dumps([{
                "question": a.question,
                "answer": a.answer,
                "confidence": a.confidence_score,
                "sources": a.sources,
                "method": a.method
            } for a in answers], indent=2)
        else:
            return self._export_plain(answers)

    def _export_markdown(self, answers: List[GeneratedAnswer]) -> str:
        """Export as formatted markdown"""
        lines = ["# RFP Response Draft\n"]
        lines.append(f"*Generated using {len(answers)} questions*\n\n---\n")

        for i, ans in enumerate(answers, 1):
            confidence_emoji = "🟢" if ans.confidence_score > 0.7 else "🟡" if ans.confidence_score > 0.4 else "🔴"

            lines.append(f"## Question {i}\n")
            lines.append(f"**{ans.question}**\n")
            lines.append(f"\n*Confidence: {confidence_emoji} {ans.confidence_score:.0%} | Method: {ans.method}*\n")
            lines.append(f"\n### Answer\n")
            lines.append(f"{ans.answer}\n")

            if ans.sources:
                lines.append(f"\n### Sources\n")
                for src in ans.sources[:3]:
                    lines.append(f"- {src['file']} ({src['similarity']:.0%} match)\n")

            lines.append("\n---\n")

        return "\n".join(lines)

    def _export_plain(self, answers: List[GeneratedAnswer]) -> str:
        """Export as plain text"""
        lines = ["RFP RESPONSE DRAFT", "=" * 50, ""]

        for i, ans in enumerate(answers, 1):
            lines.append(f"QUESTION {i}:")
            lines.append(ans.question)
            lines.append("")
            lines.append("ANSWER:")
            lines.append(ans.answer)
            lines.append("")
            lines.append(f"Confidence: {ans.confidence_score:.0%}")
            lines.append("-" * 50)
            lines.append("")

        return "\n".join(lines)
