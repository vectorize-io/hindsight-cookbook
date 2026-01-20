/**
 * Sanity CMS Client
 * Fetches blog posts from Sanity for syncing to Hindsight memory
 */
import { createClient, type QueryParams } from '@sanity/client';
import 'dotenv/config';

// Initialize Sanity client
export const sanityClient = createClient({
  projectId: process.env.SANITY_PROJECT_ID!,
  dataset: process.env.SANITY_DATASET || 'production',
  apiVersion: process.env.SANITY_API_VERSION || '2024-01-09',
  useCdn: false, // Disabled for real-time updates
});

// TypeScript interfaces for blog posts
export interface SanityPost {
  _id: string;
  _createdAt: string;
  _updatedAt: string;
  title: string;
  slug: { current: string };
  description: string;
  date: string;
  tags: string[] | null;
  readingTime: string | null;
  content: string;
}

export interface BlogPost {
  id: string;
  slug: string;
  title: string;
  description: string;
  date: string;
  tags: string[];
  content: string;
  readingTime: string;
  createdAt: string;
  updatedAt: string;
}

/**
 * Transform Sanity post to normalized BlogPost
 */
export function transformPost(sanityPost: SanityPost): BlogPost {
  return {
    id: sanityPost._id,
    slug: sanityPost.slug.current,
    title: sanityPost.title,
    description: sanityPost.description,
    date: sanityPost.date,
    tags: sanityPost.tags ?? [],
    content: sanityPost.content,
    readingTime: sanityPost.readingTime ?? '5 min read',
    createdAt: sanityPost._createdAt,
    updatedAt: sanityPost._updatedAt,
  };
}

// GROQ query for fetching posts with all fields
const postFields = `
  _id,
  _createdAt,
  _updatedAt,
  title,
  slug,
  description,
  date,
  tags,
  readingTime,
  content
`;

/**
 * Get all published posts from Sanity
 */
export async function getAllPosts(): Promise<BlogPost[]> {
  const query = `*[_type == "post" && draft != true] | order(date desc) {${postFields}}`;
  const posts = await sanityClient.fetch<SanityPost[]>(query);
  return posts.map(transformPost);
}

/**
 * Get a single post by slug
 */
export async function getPostBySlug(slug: string): Promise<BlogPost | null> {
  const query = `*[_type == "post" && slug.current == $slug][0] {${postFields}}`;
  const params: QueryParams = { slug };
  const post = await sanityClient.fetch<SanityPost | null>(query, params);
  return post ? transformPost(post) : null;
}

/**
 * Get posts by tag
 */
export async function getPostsByTag(tag: string): Promise<BlogPost[]> {
  const query = `*[_type == "post" && $tag in tags && draft != true] | order(date desc) {${postFields}}`;
  const params: QueryParams = { tag };
  const posts = await sanityClient.fetch<SanityPost[]>(query, params);
  return posts.map(transformPost);
}

/**
 * Get posts within a date range
 * Useful for temporal queries like "posts from January 2025"
 */
export async function getPostsByDateRange(
  startDate: string,
  endDate: string
): Promise<BlogPost[]> {
  const query = `*[_type == "post" && date >= $startDate && date <= $endDate && draft != true] | order(date desc) {${postFields}}`;
  const params: QueryParams = { startDate, endDate };
  const posts = await sanityClient.fetch<SanityPost[]>(query, params);
  return posts.map(transformPost);
}
