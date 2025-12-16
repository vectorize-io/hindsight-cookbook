import cron from 'node-cron';
import { query } from './db';
import { StancePipeline } from './stance-pipeline';
import { FrequencyType } from '@/types';

class JobScheduler {
  private jobs: Map<string, cron.ScheduledTask> = new Map();

  start() {
    console.log('Starting job scheduler...');

    // Run every hour to check for active sessions
    cron.schedule('0 * * * *', async () => {
      await this.processActiveSessions();
    });
  }

  async processActiveSessions() {
    try {
      const sessions = await query<any>(
        `SELECT * FROM tracking_sessions WHERE status = 'active'`
      );

      for (const session of sessions) {
        if (this.shouldRunSession(session)) {
          await this.runSession(session);
        }
      }
    } catch (error) {
      console.error('Error processing active sessions:', error);
    }
  }

  async runSession(session: any) {
    console.log(`Running session ${session.id} for topic: ${session.topic}`);

    try {
      const pipeline = new StancePipeline(session.id);

      const location = {
        country: session.country,
        state: session.state,
        city: session.city,
      };

      // Process all candidates
      await pipeline.processAllCandidates(
        session.candidates,
        session.topic,
        location
      );

      // Update last run time
      await query(
        'UPDATE tracking_sessions SET updated_at = NOW() WHERE id = $1',
        [session.id]
      );

      console.log(`Completed session ${session.id}`);
    } catch (error) {
      console.error(`Error running session ${session.id}:`, error);
    }
  }

  scheduleSession(sessionId: string, frequency: FrequencyType) {
    // Stop existing job if any
    this.stopSession(sessionId);

    let cronExpression: string;

    switch (frequency) {
      case 'hourly':
        cronExpression = '0 * * * *'; // Every hour
        break;
      case 'daily':
        cronExpression = '0 0 * * *'; // Daily at midnight
        break;
      case 'weekly':
        cronExpression = '0 0 * * 0'; // Weekly on Sunday
        break;
      default:
        cronExpression = '0 0 * * *'; // Default to daily
    }

    const task = cron.schedule(cronExpression, async () => {
      const session = await query(
        'SELECT * FROM tracking_sessions WHERE id = $1',
        [sessionId]
      );

      if (session && session[0] && session[0].status === 'active') {
        await this.runSession(session[0]);
      }
    });

    this.jobs.set(sessionId, task);
    console.log(`Scheduled session ${sessionId} with frequency: ${frequency}`);
  }

  stopSession(sessionId: string) {
    const job = this.jobs.get(sessionId);
    if (job) {
      job.stop();
      this.jobs.delete(sessionId);
      console.log(`Stopped session ${sessionId}`);
    }
  }

  private shouldRunSession(session: any): boolean {
    const now = new Date();
    const updatedAt = new Date(session.updated_at);
    const diffMs = now.getTime() - updatedAt.getTime();
    const diffHours = diffMs / (1000 * 60 * 60);

    switch (session.frequency) {
      case 'hourly':
        return diffHours >= 1;
      case 'daily':
        return diffHours >= 24;
      case 'weekly':
        return diffHours >= 168;
      default:
        return false;
    }
  }

  stopAll() {
    for (const [sessionId, job] of this.jobs.entries()) {
      job.stop();
      console.log(`Stopped session ${sessionId}`);
    }
    this.jobs.clear();
  }
}

export const scheduler = new JobScheduler();
