import fs from 'fs/promises';
import path from 'path';
import { randomUUID } from 'crypto';

interface Database {
  tracking_sessions: any[];
  stance_points: any[];
  references: any[];
  stance_point_references: any[];
  scraper_configs: any[];
}

const DB_FILE = path.join(process.cwd(), 'data', 'db.json');

let dbCache: Database | null = null;

async function ensureDataDir() {
  const dataDir = path.dirname(DB_FILE);
  try {
    await fs.access(dataDir);
  } catch {
    await fs.mkdir(dataDir, { recursive: true });
  }
}

async function loadDb(): Promise<Database> {
  if (dbCache) return dbCache;

  await ensureDataDir();

  try {
    const data = await fs.readFile(DB_FILE, 'utf-8');
    dbCache = JSON.parse(data);
    return dbCache!;
  } catch {
    // Initialize empty database
    dbCache = {
      tracking_sessions: [],
      stance_points: [],
      references: [],
      stance_point_references: [],
      scraper_configs: [],
    };
    await saveDb();
    return dbCache;
  }
}

async function saveDb() {
  if (!dbCache) return;
  await ensureDataDir();
  await fs.writeFile(DB_FILE, JSON.stringify(dbCache, null, 2), 'utf-8');
}

// Simple SQL-like query parser for basic operations
function parseInsert(sql: string, params: any[]): { table: string; data: any } {
  // Normalize whitespace for multi-line queries
  const normalized = sql.replace(/\s+/g, ' ').trim();

  // Handle INSERT with optional ON CONFLICT and RETURNING clauses
  const insertMatch = normalized.match(/INSERT INTO ["']?(\w+)["']?\s*\((.*?)\)\s*VALUES\s*\((.*?)\)(?:\s+ON CONFLICT.*?)?(?:\s+RETURNING.*?)?$/i);
  if (!insertMatch) {
    console.error('Failed to parse INSERT query:', normalized);
    throw new Error('Invalid INSERT query');
  }

  const table = insertMatch[1];
  const columns = insertMatch[2].split(',').map(c => c.trim().replace(/['"]/g, ''));

  const data: any = { id: randomUUID(), created_at: new Date().toISOString() };
  columns.forEach((col, i) => {
    data[col] = params[i];
  });

  return { table, data };
}

function parseUpdate(sql: string, params: any[]): { table: string; updates: any; where: any } {
  // Normalize whitespace for multi-line queries
  const normalized = sql.replace(/\s+/g, ' ').trim();
  const updateMatch = normalized.match(/UPDATE (\w+)\s+SET\s+(.*?)\s+WHERE\s+(.*?)$/i);
  if (!updateMatch) throw new Error('Invalid UPDATE query');

  const table = updateMatch[1];
  const setClause = updateMatch[2];
  const whereClause = updateMatch[3];

  const updates: any = { updated_at: new Date().toISOString() };
  const setParts = setClause.split(',');
  let paramIdx = 0;

  setParts.forEach(part => {
    const match = part.trim().match(/(\w+)\s*=\s*\$(\d+)|(\w+)\s*=\s*NOW\(\)/i);
    if (match) {
      if (match[3]) {
        // NOW() function
        updates[match[3]] = new Date().toISOString();
      } else {
        // Parameter
        updates[match[1]] = params[paramIdx++];
      }
    }
  });

  const whereMatch = whereClause.match(/(\w+)\s*=\s*\$(\d+)/);
  const where = whereMatch ? { [whereMatch[1]]: params[params.length - 1] } : {};

  return { table, updates, where };
}

function parseSelect(sql: string): { table: string; joins: any[]; where: string; groupBy?: string; orderBy?: string } {
  // Extract table name
  const fromMatch = sql.match(/FROM\s+(\w+)/i);
  if (!fromMatch) throw new Error('Invalid SELECT query');
  const table = fromMatch[1];

  // Extract joins
  const joins: any[] = [];
  const joinRegex = /LEFT JOIN\s+(\w+)\s+(\w+)\s+ON\s+([\w.]+)\s*=\s*([\w.]+)/gi;
  let joinMatch;
  while ((joinMatch = joinRegex.exec(sql)) !== null) {
    joins.push({
      table: joinMatch[1],
      alias: joinMatch[2],
      on: { left: joinMatch[3], right: joinMatch[4] }
    });
  }

  // Extract WHERE clause
  const whereMatch = sql.match(/WHERE\s+(.*?)(?:GROUP BY|ORDER BY|$)/i);
  const where = whereMatch ? whereMatch[1].trim() : '';

  // Extract GROUP BY
  const groupByMatch = sql.match(/GROUP BY\s+(.*?)(?:ORDER BY|$)/i);
  const groupBy = groupByMatch ? groupByMatch[1].trim() : undefined;

  // Extract ORDER BY
  const orderByMatch = sql.match(/ORDER BY\s+(.*?)$/i);
  const orderBy = orderByMatch ? orderByMatch[1].trim() : undefined;

  return { table, joins, where, groupBy, orderBy };
}

function applyWhere(data: any[], whereClause: string, params: any[]): any[] {
  if (!whereClause) return data;

  let paramIdx = 0;
  return data.filter(row => {
    // Handle simple conditions like "column = $1"
    const conditions = whereClause.split(/\s+AND\s+/i);
    return conditions.every(condition => {
      const match = condition.match(/(\w+)\s*=\s*\$(\d+)/);
      if (match) {
        const column = match[1];
        const value = params[paramIdx++];
        return row[column] === value;
      }
      return true;
    });
  });
}

function applyOrderBy(data: any[], orderBy?: string): any[] {
  if (!orderBy) return data;

  const match = orderBy.match(/(\w+)\s*(ASC|DESC)?/i);
  if (!match) return data;

  const column = match[1];
  const direction = match[2]?.toUpperCase() === 'DESC' ? -1 : 1;

  return [...data].sort((a, b) => {
    const aVal = a[column];
    const bVal = b[column];
    if (aVal < bVal) return -1 * direction;
    if (aVal > bVal) return 1 * direction;
    return 0;
  });
}

export async function query<T = any>(text: string, params: any[] = []): Promise<T[]> {
  const db = await loadDb();
  const sql = text.trim();

  if (sql.startsWith('SELECT')) {
    const { table, joins, where, groupBy, orderBy } = parseSelect(sql);
    let data = (db as any)[table] || [];

    // Apply WHERE clause
    data = applyWhere(data, where, params);

    // Handle joins for stance_points query
    if (joins.length > 0 && table === 'stance_points') {
      // Add sources to each stance point
      data = data.map((sp: any) => {
        const spRefs = db.stance_point_references.filter(spr => spr.stance_point_id === sp.id);
        const sources = spRefs.map(spr => {
          const ref = db.references.find(r => r.id === spr.reference_id);
          return ref ? {
            id: ref.id,
            url: ref.url,
            title: ref.title,
            excerpt: ref.excerpt,
            published_date: ref.published_date,
            source_type: ref.source_type,
          } : null;
        }).filter(Boolean);

        return {
          ...sp,
          sources: sources.length > 0 ? sources : [],
        };
      });
    }

    // Apply ORDER BY
    data = applyOrderBy(data, orderBy);

    return data;
  }

  if (sql.startsWith('INSERT')) {
    const { table, data } = parseInsert(sql, params);
    (db as any)[table].push(data);
    await saveDb();
    return [data];
  }

  if (sql.startsWith('UPDATE')) {
    const { table, updates, where } = parseUpdate(sql, params);
    const items = (db as any)[table];
    const item = items.find((i: any) => i[Object.keys(where)[0]] === Object.values(where)[0]);
    if (item) {
      Object.assign(item, updates);
      await saveDb();
      return [item];
    }
    return [];
  }

  if (sql.startsWith('DELETE')) {
    const deleteMatch = sql.match(/DELETE FROM (\w+) WHERE (\w+) = \$1/i);
    if (deleteMatch) {
      const table = deleteMatch[1];
      const column = deleteMatch[2];
      const value = params[0];
      (db as any)[table] = (db as any)[table].filter((item: any) => item[column] !== value);
      await saveDb();
    }
    return [];
  }

  throw new Error(`Unsupported query: ${sql}`);
}

export async function queryOne<T = any>(text: string, params?: any[]): Promise<T | null> {
  const rows = await query<T>(text, params);
  return rows.length > 0 ? rows[0] : null;
}

// Compatibility exports
export function getPool() {
  return null;
}

export async function getClient() {
  return null;
}

export async function closePool() {
  // No-op for JSON storage
}
