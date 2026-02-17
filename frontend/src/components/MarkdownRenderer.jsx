import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { useI18n } from '../i18n';

export default function MarkdownRenderer({ content }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      className="prose prose-invert prose-sm max-w-none"
      components={{
        code({ node, inline, className, children, ...props }) {
          const match = /language-(\w+)/.exec(className || '');
          return !inline && match ? (
            <CodeBlock language={match[1]}>
              {String(children).replace(/\n$/, '')}
            </CodeBlock>
          ) : (
            <code className="bg-gray-700 px-1.5 py-0.5 rounded text-emerald-300 text-sm" {...props}>
              {children}
            </code>
          );
        },
        a({ href, children }) {
          return (
            <a href={href} target="_blank" rel="noopener noreferrer" className="text-emerald-400 hover:underline">
              {children}
            </a>
          );
        },
      }}
    >
      {content || ''}
    </ReactMarkdown>
  );
}

function CodeBlock({ language, children }) {
  const { t } = useI18n();
  const [copied, setCopied] = useState(false);

  function handleCopy() {
    navigator.clipboard.writeText(children).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

  return (
    <div className="relative group my-2">
      <div className="flex items-center justify-between px-3 py-1 bg-gray-800 rounded-t-lg">
        <span className="text-[10px] text-gray-500 uppercase">{language || 'code'}</span>
        <button
          onClick={handleCopy}
          className="text-[10px] text-gray-500 hover:text-gray-200 transition-colors px-2 py-0.5"
        >
          {copied ? `\u2713 ${t('web.markdown.copied')}` : t('web.markdown.copy')}
        </button>
      </div>
      <SyntaxHighlighter
        style={oneDark}
        language={language}
        PreTag="div"
        className="rounded-b-lg text-sm"
        customStyle={{ margin: 0, borderTopLeftRadius: 0, borderTopRightRadius: 0 }}
      >
        {children}
      </SyntaxHighlighter>
    </div>
  );
}
