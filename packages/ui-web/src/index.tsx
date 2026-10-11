import type { ButtonHTMLAttributes, ReactNode } from 'react';
export function Button({ children, className = '', ...props }: ButtonHTMLAttributes<HTMLButtonElement>) {
  return <button className={`button ${className}`} {...props}>{children}</button>;
}
export function Badge({ children, tone = 'muted' }: { children: ReactNode; tone?: string }) {
  return <span className={`badge ${tone}`}>{children}</span>;
}
export type TaskCard = { schema_version: 1; kind: 'task_status'; run_id: string; status: string; title: string };
