import {memo} from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

export const Markdown=memo(function Markdown({content}:{content:string}) {
 return <div className="adex-markdown"><ReactMarkdown remarkPlugins={[remarkGfm]} components={{
  a:({href,children})=><a href={href} target="_blank" rel="noopener noreferrer">{children}</a>,
  table:({children})=><div className="markdown-table" role="region" aria-label="表格，可横向滚动" tabIndex={0}><table>{children}</table></div>,
 }}>{content}</ReactMarkdown></div>;
});
