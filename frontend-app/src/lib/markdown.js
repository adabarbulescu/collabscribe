import katex from "katex";
import { marked } from "marked";

marked.setOptions({
  breaks: true,
  gfm: true
});

function renderLatex(input) {
  const withBlocks = input.replace(/\$\$([\s\S]+?)\$\$/g, (_, expression) => {
    return katex.renderToString(expression.trim(), {
      displayMode: true,
      throwOnError: false
    });
  });

  return withBlocks.replace(/\$(.+?)\$/g, (_, expression) => {
    return katex.renderToString(expression.trim(), {
      displayMode: false,
      throwOnError: false
    });
  });
}

export function renderPreviewHtml(markdown) {
  return marked.parse(renderLatex(markdown));
}
