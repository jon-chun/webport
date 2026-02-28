"""Next.js project generator."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List

from webport.core.config import SiteConfig
from webport.core.models import StageResult
from webport.generators.base import BaseGenerator
from webport.generators.nextjs.prisma import generate_prisma_schema, generate_seed_script

logger = logging.getLogger(__name__)


class NextJSGenerator(BaseGenerator):
    """Generate a Next.js 14 project from crawl data."""

    def generate(self) -> StageResult:
        """Generate the Next.js project structure."""
        output_dir = self.site_config.output_dir / "nextjs"
        output_dir.mkdir(parents=True, exist_ok=True)

        files_created: List[str] = []
        errors: List[str] = []

        # Load data
        posts = self.load_json("wp_posts.json") or []
        pages = self.load_json("wp_pages.json") or []
        participants = self.load_json("wp_participants.json") or []
        site_info = self.load_json("wp_site_info.json") or {}

        site_name = self.site_config.name or site_info.get("name", self.site_config.domain)

        try:
            # package.json
            pkg = self._generate_package_json(site_name)
            self._write_file(output_dir / "package.json", json.dumps(pkg, indent=2))
            files_created.append("package.json")

            # tsconfig.json
            tsconfig = self._generate_tsconfig()
            self._write_file(output_dir / "tsconfig.json", json.dumps(tsconfig, indent=2))
            files_created.append("tsconfig.json")

            # next.config.js
            self._write_file(output_dir / "next.config.js", self._generate_next_config())
            files_created.append("next.config.js")

            # tailwind.config.ts
            self._write_file(
                output_dir / "tailwind.config.ts", self._generate_tailwind_config()
            )
            files_created.append("tailwind.config.ts")

            # .env.example
            self._write_file(output_dir / ".env.example", 'DATABASE_URL="file:./prisma/dev.db"\n')
            files_created.append(".env.example")

            # Prisma schema
            if self.site_config.generate.prisma:
                prisma_dir = output_dir / "prisma"
                prisma_dir.mkdir(exist_ok=True)

                schema = generate_prisma_schema(posts, participants)
                self._write_file(prisma_dir / "schema.prisma", schema)
                files_created.append("prisma/schema.prisma")

                seed = generate_seed_script(posts, participants)
                self._write_file(prisma_dir / "seed.ts", seed)
                files_created.append("prisma/seed.ts")

            # App layout
            src_dir = output_dir / "src" / "app"
            src_dir.mkdir(parents=True, exist_ok=True)

            layout = self._generate_root_layout(site_name)
            self._write_file(src_dir / "layout.tsx", layout)
            files_created.append("src/app/layout.tsx")

            page = self._generate_home_page(site_name, len(posts), len(participants))
            self._write_file(src_dir / "page.tsx", page)
            files_created.append("src/app/page.tsx")

            # globals.css
            self._write_file(src_dir / "globals.css", self._generate_globals_css())
            files_created.append("src/app/globals.css")

        except Exception as e:
            errors.append(f"Generation error: {e}")
            logger.exception("Next.js generation failed")

        return StageResult(
            stage="generate",
            success=len(errors) == 0,
            files_created=files_created,
            file_count=len(files_created),
            errors=errors,
        )

    def _write_file(self, path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

    def _generate_package_json(self, site_name: str) -> Dict[str, Any]:
        return {
            "name": site_name.lower().replace(" ", "-"),
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
                "@prisma/client": "^5.0.0",
            },
            "devDependencies": {
                "typescript": "^5.0.0",
                "@types/node": "^20.0.0",
                "@types/react": "^18.2.0",
                "@types/react-dom": "^18.2.0",
                "prisma": "^5.0.0",
                "tailwindcss": "^3.4.0",
                "postcss": "^8.4.0",
                "autoprefixer": "^10.4.0",
            },
            "prisma": {"seed": "npx tsx prisma/seed.ts"},
        }

    def _generate_tsconfig(self) -> Dict[str, Any]:
        return {
            "compilerOptions": {
                "target": "es5",
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

    def _generate_next_config(self) -> str:
        return """/** @type {import('next').NextConfig} */
const nextConfig = {
  images: {
    domains: [],
  },
}

module.exports = nextConfig
"""

    def _generate_tailwind_config(self) -> str:
        return """import type { Config } from 'tailwindcss'

const config: Config = {
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {},
  },
  plugins: [],
}
export default config
"""

    def _generate_root_layout(self, site_name: str) -> str:
        return f"""import type {{ Metadata }} from 'next'
import './globals.css'

export const metadata: Metadata = {{
  title: '{site_name}',
  description: '{site_name} - Generated by WebPort',
}}

export default function RootLayout({{
  children,
}}: {{
  children: React.ReactNode
}}) {{
  return (
    <html lang="en">
      <body>{{children}}</body>
    </html>
  )
}}
"""

    def _generate_home_page(self, site_name: str, post_count: int, participant_count: int) -> str:
        return f"""export default function Home() {{
  return (
    <main className="min-h-screen p-8">
      <h1 className="text-4xl font-bold mb-4">{site_name}</h1>
      <p className="text-lg text-gray-600 mb-8">
        Welcome to {site_name}. This site was generated by WebPort.
      </p>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="p-6 border rounded-lg">
          <h2 className="text-2xl font-semibold mb-2">Posts</h2>
          <p className="text-3xl font-bold text-blue-600">{post_count}</p>
        </div>
        <div className="p-6 border rounded-lg">
          <h2 className="text-2xl font-semibold mb-2">Participants</h2>
          <p className="text-3xl font-bold text-blue-600">{participant_count}</p>
        </div>
      </div>
    </main>
  )
}}
"""

    def _generate_globals_css(self) -> str:
        return """@tailwind base;
@tailwind components;
@tailwind utilities;
"""
