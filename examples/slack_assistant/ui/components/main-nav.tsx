"use client";

// import GitHubButton from "react-github-btn";

import Image from "next/image";
import Link from "next/link";

import { cn } from "@/lib/utils";

export function MainNav({
  className,
  ...props
}: React.HTMLAttributes<HTMLElement>) {
  return (
    <nav
      className={cn("flex items-center space-x-4 lg:space-x-6", className)}
      {...props}
    >
      <Link href="/">
        <Image
          src="https://app.embedchain.ai/logo.svg"
          alt="Logo"
          width={125}
          height={125}
        />
      </Link>
      <Link
        href="/admin"
        className="text-sm font-light text-muted-foreground transition-colors hover:text-primary hover:text-black"
      >
        Admin
      </Link>
      <Link
        href="https://github.com/embedchain/embedchain"
        className="text-sm font-light text-muted-foreground transition-colors hover:text-primary hover:text-black"
        target="_blank"
      >
        GitHub
      </Link>
      {/* <Link
        href="https://github.com/embedchain/embedchain"
        className="text-sm font-light text-muted-foreground transition-colors hover:text-primary hover:text-black"
        target="_blank"
      >
        GitHub
      </Link>
      <Link
        href="https://github.com/embedchain/embedchain"
        className="text-sm font-light text-muted-foreground transition-colors hover:text-primary hover:text-black"
        target="_blank"
      >
        GitHub
      </Link>
      <Link
        href="https://join.slack.com/t/embedchain/shared_invite/zt-22uwz3c46-Zg7cIh5rOBteT_xe1jwLDw"
        className="text-sm font-light text-muted-foreground transition-colors hover:text-primary hover:text-black"
        target="_blank"
      >
        Slack
      </Link>
      <Link
        href="https://docs.embedchain.ai"
        className="text-sm font-light text-muted-foreground transition-colors hover:text-primary hover:text-black"
        target="_blank"
      >
        Docs
      </Link> */}
    </nav>
  );
}
