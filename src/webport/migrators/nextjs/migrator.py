"""
WebPort Next.js Migrator

Generates Next.js 14+ projects with App Router or Pages Router.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import List, Optional

from webport.core.config import MigrationConfig
from webport.core.models import CrawlResult, WordPressPost
from webport.migrators.base import BaseMigrator

logger = logging.getLogger(__name__)


class NextJSMigrator(BaseMigrator):
    """
    Next.js migrator supporting:
    - App Router (Next.js 13+)
    - Pages Router (legacy)
    - TypeScript
    - Tailwind CSS
    - MDX content
    """
    
    @property
    def name(self) -> str:
        return "nextjs"
    
    def _get_template_dir(self) -> Path:
        return Path(__file__).parent / "nextjs" / "templates"
    
    async def _setup_project(self) -> None:
        """Create Next.js project structure."""
        logger.info("Setting up Next.js project structure...")
        
        # package.json
        package_json = {
            "name": self._slugify(self.crawl_result.target_url.split("//")[1].split("/")[0]),
            "version": "0.1.0",
            "private": True,
            "scripts": {
                "dev": "next dev",
                "build": "next build",
                "start": "next start",
                "lint": "next lint",
            },
            "dependencies": {
                "next": "^14.0.0",
                "react": "^18.2.0",
                "react-dom": "^18.2.0",
            },
            "devDependencies": {},
        }
        
        if self.config.typescript:
            package_json["devDependencies"].update({
                "typescript": "^5.3.0",
                "@types/node": "^20.10.0",
                "@types/react": "^18.2.0",
                "@types/react-dom": "^18.2.0",
            })
        
        if self.config.styling == "tailwind":
            package_json["devDependencies"].update({
                "tailwindcss": "^3.4.0",
                "postcss": "^8.4.0",
                "autoprefixer": "^10.4.0",
            })
        
        if self.config.content_format in ("mdx", "markdown"):
            package_json["dependencies"]["@next/mdx"] = "^14.0.0"
            package_json["dependencies"]["@mdx-js/loader"] = "^3.0.0"
            package_json["dependencies"]["@mdx-js/react"] = "^3.0.0"
        
        self._write_file(
            self.output_dir / "package.json",
            json.dumps(package_json, indent=2),
        )
        
        # next.config.js
        next_config = self._generate_next_config()
        ext = ".ts" if self.config.typescript else ".js"
        self._write_file(self.output_dir / f"next.config{ext}", next_config)
        
        # TypeScript config
        if self.config.typescript:
            tsconfig = {
                "compilerOptions": {
                    "target": "ES2017",
                    "lib": ["dom", "dom.iterable", "esnext"],
                    "allowJs": True,
                    "skipLibCheck": True,
                    "strict": True,
                    "noEmit": True,
                    "esModuleInterop": True,
                    "module": "esnext",
                    "moduleResolution": "bundler",
                    "resolveJsonModule": True,
                    "isolatedModules": True,
                    "jsx": "preserve",
                    "incremental": True,
                    "plugins": [{"name": "next"}],
                    "paths": {"@/*": ["./src/*"]},
                },
                "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx", ".next/types/**/*.ts"],
                "exclude": ["node_modules"],
            }
            self._write_file(
                self.output_dir / "tsconfig.json",
                json.dumps(tsconfig, indent=2),
            )
        
        # Tailwind config
        if self.config.styling == "tailwind":
            self._write_file(
                self.output_dir / "tailwind.config.js",
                self._generate_tailwind_config(),
            )
            self._write_file(
                self.output_dir / "postcss.config.js",
                """module.exports = {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
}
""",
            )
        
        # Create directory structure
        if self.config.nextjs_router == "app":
            await self._setup_app_router()
        else:
            await self._setup_pages_router()
        
        # README
        self._write_file(
            self.output_dir / "README.md",
            self._generate_readme(),
        )
    
    async def _setup_app_router(self) -> None:
        """Setup App Router structure."""
        ext = ".tsx" if self.config.typescript else ".jsx"
        
        # app/layout
        layout = f'''import type {{ Metadata }} from "next"
import {{ Inter }} from "next/font/google"
{"import './globals.css'" if self.config.styling == "tailwind" else ""}

const inter = Inter({{ subsets: ["latin"] }})

export const metadata: Metadata = {{
  title: "Migrated Site",
  description: "Generated by WebPort",
}}

export default function RootLayout({{
  children,
}}: {{
  children: React.ReactNode
}}) {{
  return (
    <html lang="en">
      <body className={{inter.className}}>{{children}}</body>
    </html>
  )
}}
'''
        self._write_file(self.output_dir / "src" / "app" / f"layout{ext}", layout)
        
        # globals.css
        if self.config.styling == "tailwind":
            self._write_file(
                self.output_dir / "src" / "app" / "globals.css",
                """@tailwind base;
@tailwind components;
@tailwind utilities;
""",
            )
        
        # app/page
        home_page = '''export default function Home() {
  return (
    <main className="min-h-screen p-8">
      <h1 className="text-4xl font-bold">Welcome</h1>
      <p className="mt-4">Site migrated with WebPort</p>
    </main>
  )
}
'''
        self._write_file(self.output_dir / "src" / "app" / f"page{ext}", home_page)
    
    async def _setup_pages_router(self) -> None:
        """Setup Pages Router structure."""
        ext = ".tsx" if self.config.typescript else ".jsx"
        
        # pages/_app
        app_content = f'''import type {{ AppProps }} from "next/app"
{"import '../styles/globals.css'" if self.config.styling == "tailwind" else ""}

export default function App({{ Component, pageProps }}: AppProps) {{
  return <Component {{...pageProps}} />
}}
'''
        self._write_file(self.output_dir / "src" / "pages" / f"_app{ext}", app_content)
        
        # pages/index
        index_content = '''export default function Home() {
  return (
    <main className="min-h-screen p-8">
      <h1 className="text-4xl font-bold">Welcome</h1>
      <p className="mt-4">Site migrated with WebPort</p>
    </main>
  )
}
'''
        self._write_file(self.output_dir / "src" / "pages" / f"index{ext}", index_content)
        
        # styles/globals.css
        if self.config.styling == "tailwind":
            (self.output_dir / "src" / "styles").mkdir(parents=True, exist_ok=True)
            self._write_file(
                self.output_dir / "src" / "styles" / "globals.css",
                """@tailwind base;
@tailwind components;
@tailwind utilities;
""",
            )
    
    async def _generate_pages(self) -> None:
        """Generate page components from crawled content."""
        logger.info("Generating pages...")
        
        ext = ".tsx" if self.config.typescript else ".jsx"
        
        # Generate from WordPress posts if available
        if hasattr(self.crawl_result, "posts") and self.crawl_result.posts:
            await self._generate_blog_pages(self.crawl_result.posts)
        
        # Generate from crawled pages
        for page in self.crawl_result.pages[:50]:  # Limit for now
            if not page.content:
                continue
            
            slug = self._slugify(page.metadata.title or "page")
            
            if self.config.nextjs_router == "app":
                page_dir = self.output_dir / "src" / "app" / slug
                page_dir.mkdir(parents=True, exist_ok=True)
                
                content = self._generate_app_page(page)
                self._write_file(page_dir / f"page{ext}", content)
            else:
                content = self._generate_pages_page(page)
                self._write_file(
                    self.output_dir / "src" / "pages" / f"{slug}{ext}",
                    content,
                )
    
    async def _generate_blog_pages(self, posts: List[WordPressPost]) -> None:
        """Generate blog pages from WordPress posts."""
        ext = ".tsx" if self.config.typescript else ".jsx"
        content_dir = self.output_dir / "content" / "posts"
        content_dir.mkdir(parents=True, exist_ok=True)
        
        for post in posts[:100]:  # Limit
            # Create MDX/MD file
            if self.config.content_format in ("mdx", "markdown"):
                frontmatter = f"""---
title: "{post.title.replace('"', '\\"')}"
date: "{post.date or ''}"
slug: "{post.slug}"
excerpt: "{(post.excerpt or '').replace('"', '\\"')[:200]}"
---

"""
                content = frontmatter + self._html_to_markdown(post.content)
                
                file_ext = ".mdx" if self.config.content_format == "mdx" else ".md"
                self._write_file(content_dir / f"{post.slug}{file_ext}", content)
            else:
                # Generate React component
                content = self._generate_post_component(post)
                
                if self.config.nextjs_router == "app":
                    post_dir = self.output_dir / "src" / "app" / "blog" / post.slug
                    post_dir.mkdir(parents=True, exist_ok=True)
                    self._write_file(post_dir / f"page{ext}", content)
                else:
                    (self.output_dir / "src" / "pages" / "blog").mkdir(parents=True, exist_ok=True)
                    self._write_file(
                        self.output_dir / "src" / "pages" / "blog" / f"{post.slug}{ext}",
                        content,
                    )
    
    def _generate_app_page(self, page) -> str:
        """Generate App Router page component."""
        title = page.metadata.title or "Page"
        content_text = self._html_to_markdown(page.content.raw_html) if page.content else ""
        
        return f'''export default function Page() {{
  return (
    <main className="min-h-screen p-8">
      <h1 className="text-4xl font-bold">{title}</h1>
      <div className="prose mt-8">
        {content_text[:1000]}
      </div>
    </main>
  )
}}
'''
    
    def _generate_pages_page(self, page) -> str:
        """Generate Pages Router page component."""
        return self._generate_app_page(page)
    
    def _generate_post_component(self, post: WordPressPost) -> str:
        """Generate component for a blog post."""
        return f'''export default function Post() {{
  return (
    <article className="max-w-3xl mx-auto p-8">
      <h1 className="text-4xl font-bold">{post.title}</h1>
      <time className="text-gray-500">{post.date or ""}</time>
      <div className="prose mt-8" dangerouslySetInnerHTML={{{{ __html: `{post.content[:2000]}` }}}} />
    </article>
  )
}}
'''
    
    async def _generate_components(self) -> None:
        """Generate shared components."""
        logger.info("Generating components...")
        
        ext = ".tsx" if self.config.typescript else ".jsx"
        components_dir = self.output_dir / "src" / "components"
        components_dir.mkdir(parents=True, exist_ok=True)
        
        # Header component
        header = '''export function Header() {
  return (
    <header className="bg-white shadow">
      <nav className="max-w-7xl mx-auto px-4 py-4">
        <a href="/" className="text-xl font-bold">Site Name</a>
      </nav>
    </header>
  )
}
'''
        self._write_file(components_dir / f"Header{ext}", header)
        
        # Footer component
        footer = '''export function Footer() {
  return (
    <footer className="bg-gray-100 mt-auto">
      <div className="max-w-7xl mx-auto px-4 py-8">
        <p className="text-gray-600">© 2024 Site Name. Migrated with WebPort.</p>
      </div>
    </footer>
  )
}
'''
        self._write_file(components_dir / f"Footer{ext}", footer)
    
    async def _copy_assets(self) -> None:
        """Copy static assets."""
        logger.info("Copying assets...")
        
        public_dir = self.output_dir / "public"
        public_dir.mkdir(parents=True, exist_ok=True)
        
        # Create placeholder favicon
        # In production, would copy actual downloaded media
    
    def _generate_next_config(self) -> str:
        """Generate next.config.js."""
        config_parts = ["/** @type {import('next').NextConfig} */"]
        
        config = {
            "reactStrictMode": True,
        }
        
        if self.config.content_format == "mdx":
            return f"""const withMDX = require('@next/mdx')()

/** @type {{import('next').NextConfig}} */
const nextConfig = {{
  pageExtensions: ['js', 'jsx', 'mdx', 'ts', 'tsx'],
  reactStrictMode: true,
}}

module.exports = withMDX(nextConfig)
"""
        
        return f"""/** @type {{import('next').NextConfig}} */
const nextConfig = {{
  reactStrictMode: true,
}}

module.exports = nextConfig
"""
    
    def _generate_tailwind_config(self) -> str:
        """Generate tailwind.config.js."""
        return """/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
    './content/**/*.{md,mdx}',
  ],
  theme: {
    extend: {},
  },
  plugins: [
    require('@tailwindcss/typography'),
  ],
}
"""
    
    def _generate_readme(self) -> str:
        """Generate README.md."""
        return f"""# Migrated Site

This project was generated by [WebPort](https://github.com/webport/webport) from {self.crawl_result.target_url}.

## Getting Started

```bash
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

## Project Structure

- `src/app/` - App Router pages and layouts
- `src/components/` - Reusable React components
- `content/` - MDX/Markdown content files
- `public/` - Static assets

## Learn More

- [Next.js Documentation](https://nextjs.org/docs)
- [WebPort Documentation](https://webport.dev/docs)
"""


__all__ = ["NextJSMigrator"]
