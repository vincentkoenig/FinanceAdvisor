// Link zu einem Bereich: innerhalb des neuen Frontends über den Router, sonst zur bisherigen Seite.
import type { ReactNode } from 'react';
import { Link } from 'react-router';
import { AREAS, type Area } from '../lib/areas';

type Props = { area: Area; className?: string; role?: string; children: ReactNode };

export function AreaLink({ area, className, role, children }: Props) {
  const target = AREAS[area];
  if ('to' in target) return <Link to={target.to} className={className} role={role}>{children}</Link>;
  return <a href={target.href} className={className} role={role}>{children}</a>;
}
