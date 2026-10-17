import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

// Generated Markdown must not make automatic outbound requests to document-controlled URLs.
export function AnswerMarkdown({ children }: { children: string }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      disallowedElements={["img"]}
      components={{
        a: ({ children, href }) => (
          <a href={href} target="_blank" rel="noopener noreferrer">
            {children}
          </a>
        ),
      }}
    >
      {children}
    </ReactMarkdown>
  );
}
