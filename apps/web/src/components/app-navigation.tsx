"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

interface NavigationItem {
  label: string;
  href?: string;
  available: boolean;
  status?: string;
}

export function AppNavigation({
  canManageMembers,
}: {
  canManageMembers: boolean;
}): React.ReactElement {
  const pathname = usePathname();
  const items: NavigationItem[] = [
    { label: "Overview", href: "/dashboard", available: true },
    { label: "Projects", available: true, status: "Next" },
    { label: "Evaluation runs", available: true, status: "Planned" },
    { label: "Dataset review", available: false, status: "Planned" },
    {
      label: "Members",
      href: canManageMembers ? "/dashboard/members" : undefined,
      available: canManageMembers,
    },
  ];

  return (
    <nav className="nav-list" aria-label="Primary navigation">
      {items.map((item) => {
        const active = item.href
          ? item.href === "/dashboard"
            ? pathname === item.href
            : pathname.startsWith(item.href)
          : false;
        const className = `nav-item ${active ? "active" : ""} ${!item.available ? "restricted" : ""}`;
        const content = (
          <>
            <span className="nav-dot" aria-hidden="true" />
            <span>{item.label}</span>
            {item.status ? <small>{item.status}</small> : null}
            {!item.available && !item.status ? <small>Restricted</small> : null}
          </>
        );

        return item.href ? (
          <Link className={className} href={item.href} key={item.label}>
            {content}
          </Link>
        ) : (
          <div
            className={className}
            key={item.label}
            aria-disabled="true"
          >
            {content}
          </div>
        );
      })}
    </nav>
  );
}
