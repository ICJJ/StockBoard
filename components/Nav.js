"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/", label: "看板" },
  { href: "/backtest", label: "回测" },
  { href: "/paper", label: "模拟盘" },
  { href: "/live", label: "实盘" },
  { href: "/sentiment", label: "舆情" },
];

export default function Nav() {
  const path = usePathname();
  return (
    <nav className="topnav">
      {LINKS.map((l) => (
        <Link
          key={l.href}
          href={l.href}
          className={`topnav-link ${path === l.href ? "active" : ""}`}
        >
          {l.label}
        </Link>
      ))}
    </nav>
  );
}
