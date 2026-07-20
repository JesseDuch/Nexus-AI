import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import "highlight.js/styles/github-dark.css";

function isVideo(src?: string): boolean {
  return !!src && /\.(mp4|webm|mov)(\?|#|$)/i.test(src);
}

export function Markdown({ content }: { content: string }) {
  return (
    <div className="markdown-body">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeHighlight]}
        components={{
          // Generated media arrives as image-markdown; .mp4 becomes a video player.
          img: ({ src, alt }) =>
            isVideo(typeof src === "string" ? src : undefined) ? (
              <video
                src={src}
                controls
                playsInline
                preload="metadata"
                className="rounded-xl border border-border/60 max-h-96 my-2 shadow-md w-full max-w-md bg-black"
                aria-label={alt || "generated video"}
              />
            ) : (
              // eslint-disable-next-line jsx-a11y/alt-text
              <img src={src} alt={alt || ""} loading="lazy" />
            ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
