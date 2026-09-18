import { unified } from 'unified';
import remarkParse from 'remark-parse';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import remarkRehype from 'remark-rehype';
import rehypeRaw from 'rehype-raw';
import rehypeKatex from 'rehype-katex';

/**
 * Parses markdown text and removes incomplete tokens to prevent partial rendering
 * of links, images, bold, and italic formatting during streaming.
 */
function parseIncompleteMarkdown(text) {
  if (!text || typeof text !== 'string') {
    return text;
  }

  let result = text;

  // Handle incomplete links and images
  const linkImagePattern = /(!?\[)([^\]]*?)$/;
  const linkMatch = result.match(linkImagePattern);
  if (linkMatch) {
    const startIndex = result.lastIndexOf(linkMatch[1]);
    result = result.substring(0, startIndex);
  }

  // Handle incomplete bold formatting (**)
  const boldPattern = /(\*\*)([^*]*?)$/;
  const boldMatch = result.match(boldPattern);
  if (boldMatch) {
    const asteriskPairs = (result.match(/\*\*/g) || []).length;
    if (asteriskPairs % 2 === 1) {
      result = `${result}**`;
    }
  }

  // Handle incomplete italic formatting (__)
  const italicPattern = /(__)([^_]*?)$/;
  const italicMatch = result.match(italicPattern);
  if (italicMatch) {
    const underscorePairs = (result.match(/__/g) || []).length;
    if (underscorePairs % 2 === 1) {
      result = `${result}__`;
    }
  }

  // Handle incomplete single asterisk italic (*)
  const singleAsteriskPattern = /(\*)([^*]*?)$/;
  const singleAsteriskMatch = result.match(singleAsteriskPattern);
  if (singleAsteriskMatch) {
    const singleAsterisks = result.split('').reduce((acc, char, index) => {
      if (char === '*') {
        const prevChar = result[index - 1];
        const nextChar = result[index + 1];
        if (prevChar !== '*' && nextChar !== '*') {
          return acc + 1;
        }
      }
      return acc;
    }, 0);

    if (singleAsterisks % 2 === 1) {
      result = `${result}*`;
    }
  }

  // Handle incomplete single underscore italic (_)
  const singleUnderscorePattern = /(_)([^_]*?)$/;
  const singleUnderscoreMatch = result.match(singleUnderscorePattern);
  if (singleUnderscoreMatch) {
    const singleUnderscores = result.split('').reduce((acc, char, index) => {
      if (char === '_') {
        const prevChar = result[index - 1];
        const nextChar = result[index + 1];
        if (prevChar !== '_' && nextChar !== '_') {
          return acc + 1;
        }
      }
      return acc;
    }, 0);

    if (singleUnderscores % 2 === 1) {
      result = `${result}_`;
    }
  }

  // Handle incomplete inline code blocks (`) - but avoid code blocks (```)
  const inlineCodePattern = /(`)([^`]*?)$/;
  const inlineCodeMatch = result.match(inlineCodePattern);
  if (inlineCodeMatch) {
    const allTripleBackticks = (result.match(/```/g) || []).length;
    const insideIncompleteCodeBlock = allTripleBackticks % 2 === 1;

    if (!insideIncompleteCodeBlock) {
      let singleBacktickCount = 0;
      for (let i = 0; i < result.length; i++) {
        if (result[i] === '`') {
          const isTripleStart = result.substring(i, i + 3) === '```';
          const isTripleMiddle = i > 0 && result.substring(i - 1, i + 2) === '```';
          const isTripleEnd = i > 1 && result.substring(i - 2, i + 1) === '```';

          if (!(isTripleStart || isTripleMiddle || isTripleEnd)) {
            singleBacktickCount++;
          }
        }
      }

      if (singleBacktickCount % 2 === 1) {
        result = `${result}\``;
      }
    }
  }

  // Handle incomplete strikethrough formatting (~~)
  const strikethroughPattern = /(~~)([^~]*?)$/;
  const strikethroughMatch = result.match(strikethroughPattern);
  if (strikethroughMatch) {
    const tildePairs = (result.match(/~~/g) || []).length;
    if (tildePairs % 2 === 1) {
      result = `${result}~~`;
    }
  }

  return result;
}

self.onmessage = async (e) => {
  const rawText = e.data;
  const cleanText = parseIncompleteMarkdown(rawText);
  // const cleanText = rawText;
  try {
    // 1. Parse text into Markdown AST
    const mdast = unified()
      .use(remarkParse)
      .use(remarkGfm)
      .use(remarkMath)
      .parse(cleanText);

    // 2. Transform Markdown AST into HTML AST (HAST) and compile Math
    // Use allowDangerousHtml to preserve raw HTML, then rehype-raw to parse it
    const hast = await unified()
      .use(remarkRehype, { allowDangerousHtml: true })
      .use(rehypeRaw)
      .use(rehypeKatex)
      .run(mdast);

    // Send the cleanly structured JSON back to the UI
    self.postMessage({ type: 'SUCCESS', payload: hast });
  } catch (error) {
    self.postMessage({ type: 'ERROR', payload: error.message });
  }
};  

export { parseIncompleteMarkdown };