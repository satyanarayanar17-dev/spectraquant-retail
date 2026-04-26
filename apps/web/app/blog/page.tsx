import fs from "fs";
import path from "path";
import matter from "gray-matter";
import Link from "next/link";
import type { Metadata } from "next";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export const metadata: Metadata = {
  title: "Blog — SpectraQuant Retail",
  description: "Insights on factor investing and portfolio analytics for Indian equity investors.",
};

const BLOG_DIR = path.join(process.cwd(), "../../docs/blog");

type PostMeta = {
  slug: string;
  title: string;
  date: string;
  excerpt: string;
};

function getAllPosts(): PostMeta[] {
  try {
    const files = fs
      .readdirSync(BLOG_DIR)
      .filter((f) => f.endsWith(".mdx"));

    return files
      .map((filename) => {
        const slug = filename.replace(/\.mdx$/, "");
        const raw = fs.readFileSync(path.join(BLOG_DIR, filename), "utf-8");
        const { data, content } = matter(raw);

        const excerpt =
          (data.excerpt as string | undefined) ??
          content.replace(/^#+\s.*/gm, "").replace(/\n+/g, " ").trim().slice(0, 160);

        return {
          slug,
          title: (data.title as string | undefined) ?? slug,
          date: (data.date as string | undefined) ?? "",
          excerpt,
        };
      })
      .sort((a, b) => (a.date > b.date ? -1 : 1));
  } catch {
    return [];
  }
}

export default function BlogIndexPage() {
  const posts = getAllPosts();

  return (
    <section className="space-y-8 max-w-2xl">
      <div>
        <p className="text-xs uppercase tracking-[0.24em] text-tertiary">Blog</p>
        <h2 className="mt-2 text-3xl font-semibold text-primary">Factor analytics insights</h2>
        <p className="mt-2 text-sm text-secondary">
          Articles on factor investing and portfolio analytics for Indian equity investors.
        </p>
      </div>

      {posts.length === 0 ? (
        <Card>
          <CardContent className="p-6 text-secondary">No posts published yet.</CardContent>
        </Card>
      ) : (
        <ul className="space-y-4">
          {posts.map((post) => {
            const dateFormatted = post.date
              ? new Date(post.date).toLocaleDateString("en-IN", {
                  year: "numeric",
                  month: "long",
                  day: "numeric",
                })
              : null;

            return (
              <li key={post.slug}>
                <Link href={`/blog/${post.slug}`} className="block group">
                  <Card className="transition-colors group-hover:border-border">
                    <CardHeader className="pb-2">
                      <CardTitle className="text-lg group-hover:text-primary transition-colors">
                        {post.title}
                      </CardTitle>
                      {dateFormatted && (
                        <p className="text-xs text-tertiary">{dateFormatted}</p>
                      )}
                    </CardHeader>
                    <CardContent>
                      <p className="text-sm text-secondary line-clamp-2">{post.excerpt}</p>
                    </CardContent>
                  </Card>
                </Link>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
