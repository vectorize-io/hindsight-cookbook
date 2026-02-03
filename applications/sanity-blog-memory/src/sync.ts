/**
 * Blog Post Sync Script
 * Syncs all blog posts from Sanity CMS to Hindsight memory
 * 
 * Usage: npm run sync
 * 
 * Features:
 * - Document-based upsert (uses document_id for idempotent updates)
 * - Rich content structure for optimal recall
 * - Progress logging
 * - Error handling with detailed messages
 */
import { getAllPosts, type BlogPost } from './sanity-client.js';
import { 
  retainBlogPost, 
  setupBlogMemoryBank, 
  listMemories,
  bankId 
} from './hindsight-client.js';

/**
 * Format a blog post as rich content for Hindsight memory
 * The format is optimized for semantic search and recall
 */
function formatPostContent(post: BlogPost, baseUrl: string): string {
  const tags = post.tags.length > 0 ? post.tags.join(', ') : 'none';
  
  return `# Blog Post: ${post.title}

**Published:** ${post.date}
**URL:** ${baseUrl}/blog/${post.slug}
**Tags:** ${tags}
**Reading Time:** ${post.readingTime}

## Description
${post.description}

## Content
${post.content}
`;
}

/**
 * Sync a single blog post to Hindsight
 */
async function syncPost(post: BlogPost, baseUrl: string): Promise<void> {
  const content = formatPostContent(post, baseUrl);
  
  await retainBlogPost(content, {
    documentId: `post:${post.slug}`,  // Enables upsert on re-sync
    context: 'blog-post',
    timestamp: post.date,  // For temporal queries
  });
}

/**
 * Main sync function - syncs all posts from Sanity to Hindsight
 */
async function syncAllPosts(): Promise<void> {
  const baseUrl = process.env.SITE_URL || 'https://example.com';
  
  console.log('=======================================');
  console.log('  Sanity -> Hindsight Blog Sync');
  console.log('=======================================\n');
  
  // Step 1: Set up the memory bank
  console.log('Setting up memory bank...');
  await setupBlogMemoryBank(
    'Blog Memory',
    'This memory bank contains all blog posts and content. Use it to recall related content, find posts by topic, and generate insights about the blog.'
  );
  console.log(`Memory bank "${bankId}" ready\n`);
  
  // Step 2: Fetch all posts from Sanity
  console.log('Fetching posts from Sanity CMS...');
  const posts = await getAllPosts();
  console.log(`Found ${posts.length} posts to sync\n`);
  
  if (posts.length === 0) {
    console.log('No posts found. Make sure your Sanity project has published posts.');
    return;
  }
  
  // Step 3: Sync each post
  console.log('Syncing posts to Hindsight...');
  let synced = 0;
  let failed = 0;
  
  for (const post of posts) {
    try {
      process.stdout.write(`  [${synced + 1}/${posts.length}] "${post.title}"... `);
      await syncPost(post, baseUrl);
      console.log('done');
      synced++;
    } catch (error) {
      console.log('FAILED');
      console.error(`    Error: ${error instanceof Error ? error.message : String(error)}`);
      failed++;
    }
  }
  
  // Step 4: Summary
  console.log('\n=======================================');
  console.log('  Sync Complete');
  console.log('=======================================');
  console.log(`  Synced: ${synced} posts`);
  if (failed > 0) {
    console.log(`  Failed: ${failed} posts`);
  }
  
  // Step 5: Verify by listing memories
  console.log('\nVerifying sync...');
  const memories = await listMemories({ limit: 10 });
  console.log(`Total memories in bank: ${memories.total}`);
  
  console.log('\nSync complete! You can now query your blog content.');
  console.log('Try: npm run query');
}

// Run the sync
syncAllPosts().catch((error) => {
  console.error('\nFatal error during sync:');
  console.error(error);
  process.exit(1);
});
