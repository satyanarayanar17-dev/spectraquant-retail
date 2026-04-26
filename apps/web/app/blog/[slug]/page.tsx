import { notFound } from "next/navigation";
import fs from "fs";
import path from "path";
import matter from "gray-matter";
import { MDXRemote } from "next-mdx-remote/rsc";
import type { Metadata } from "next";
import Link from "next/link";

const BLOG_DIR = path.join(process.cwd(), "../../docs/blog");

function getAllSlugs(): string[] {
  try {
    return fs
      .readdirSync(BLOG_DIR)
      .filter((f) => f.endsWith(".mdx"))
      .map((f) => f.replace(/\.mdx$/, ""));
  } catch {
    return [];
  }
}

function getPost(slug: string): { frontmatter: Record<string, string>; content: string } | null {
  const filePath = path.join(BLOG_DIR, `${slug}.mdx`);
  if (!fs.existsSync(filePath)) return null;

  const raw = fs.readFileSync(filePath, "utf-8");
  const { data, content } = matter(raw);
  return { frontmatter: data as Record<string, string>, content };
}

export async function generateStaticParams() {
  return getAllSlugs().map((slug) => ({ slug }));
}

export async function generateMetadata({
  params,
}: {
  params: { slug: string };
}): Promise<Metadata> {
  const post = getPost(params.slug);
  if (!post) return {};

  return {
    title: `${post.frontmatter.title} — SpectraQuant Retail`,
    description: post.frontmatter.excerpt ?? "",
    openGraph: {
      title: post.frontmatter.title,
      description: post.frontmatter.excerpt ?? "",
      type: "article",
      publishedTime: post.frontmatter.date,
    },
    twitter: {
      card: "summary",
      title: post.frontmatter.title,
      description: post.frontmatter.excerpt ?? "",
    },
  };
}

export default function BlogPostPage({ params }: { params: { slug: string } }) {
  const post = getPost(params.slug);
  if (!post) notFound();

  const dateFormatted = post.frontmatter.date
    ? new Date(post.frontmatter.date).toLocaleDateString("en-IN", {
        year: "numeric",
        month: "long",
        day: "numeric",
      })
    : null;

  return (
    <article className="max-w-2xl space-y-8">
      <div className="space-y-3">
        <Link
          href="/blog"
          className="text-xs uppercase tracking-[0.24em] text-tertiary hover:text-secondary transition-colors"
        >
          ← Blog
        </Link>
        <h1 className="text-3xl font-semibold text-primary">{post.frontmatter.title}</h1>
        {dateFormatted && (
          <p className="text-sm text-tertiary">{dateFormatted}</p>
        )}
      </div>

      <div className="prose prose-invert prose-sm max-w-none text-secondary [&_h2]:text-primary [&_h3]:text-primary [&_strong]:text-primary">
        <MDXRemote source={post.content} />
      </div>

      <div className="border-t border-border-subtle pt-6">
        <Link href="/blog" className="text-sm text-secondary hover:text-primary transition-colors">
          ← Back to all posts
        </Link>
      </div>
    </article>
  );
}
