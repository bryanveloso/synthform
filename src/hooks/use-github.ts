import { useQuery } from '@tanstack/react-query'
import { fetchRecentCommits } from '@/api/synthhome'
import type { GitHubCommit } from '@/api/synthhome'

export type { GitHubCommit }

export function useGitHubCommits(limit = 20) {
  return useQuery<GitHubCommit[]>({
    queryKey: ['github', 'commits', limit],
    queryFn: () => fetchRecentCommits(limit),
    staleTime: 60_000,
    refetchInterval: 60_000,
  })
}
