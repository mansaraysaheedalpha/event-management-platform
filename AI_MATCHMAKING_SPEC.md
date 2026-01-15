# AI-Powered Matchmaking System Specification

## Overview

This specification outlines an intelligent matchmaking system that uses LLM-based recommendations and automated profile enrichment to create meaningful connections between event attendees.

**Important:** This system is for **ATTENDEES only**. Organizers have a separate onboarding flow focused on event creation, not networking. The matchmaking features are what differentiate this platform from competitors like Cvent and Eventbrite, where attendees barely use the app beyond checking schedules.

**Core Principles:**
- LLM for quality recommendations (not real-time scoring)
- Research agent for profile enrichment (not scraping - browsing public info like a human)
- Pre-computed and cached (not in hot path)
- Opt-in enrichment with clear value messaging (respects privacy)

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     DATA COLLECTION                              │
├─────────────────────────────────────────────────────────────────┤
│  Registration Form        Optional Enrichment      Auto-Research │
│  ├─ Name, Email          ├─ Bio                   ├─ LinkedIn    │
│  ├─ Company, Role        ├─ Industry              ├─ GitHub      │
│  ├─ 3 Interests          ├─ Skills to offer       ├─ Twitter/X   │
│  └─ Goals (multi-select) └─ Skills needed         ├─ YouTube     │
│                                                   ├─ Instagram   │
│                                                   ├─ Facebook    │
│                                                   └─ Web search  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   PROFILE ENRICHMENT AGENT                       │
│                      (LangGraph + Tavily)                        │
├─────────────────────────────────────────────────────────────────┤
│  Triggered: When user opts in OR links profile                   │
│  Process: Search public info → Extract → Structure → Store       │
│  Runs: Once per user (cached indefinitely)                       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                  RECOMMENDATION ENGINE                           │
│                     (LLM + Caching)                              │
├─────────────────────────────────────────────────────────────────┤
│  Triggered: Event check-in, daily refresh, or manual request     │
│  Process: Gather all profiles → LLM ranks matches → Cache        │
│  Output: Top 10 recommendations with explanations                │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      USER EXPERIENCE                             │
├─────────────────────────────────────────────────────────────────┤
│  Proximity Tab          │  Recommendations Tab                   │
│  ├─ Nearby users        │  ├─ "Suggested for You" (LLM picks)   │
│  ├─ Real-time updates   │  ├─ Why you should connect            │
│  └─ Ping to connect     │  └─ Conversation starters             │
└─────────────────────────────────────────────────────────────────┘
```

---

## Phase 1: Enhanced Registration

### 1.1 Database Schema Updates

Add to `shared-libs/prisma-client/prisma/schema.prisma`:

```prisma
model UserProfile {
  id                String   @id @default(cuid())
  userId            String   @unique

  // From registration (required)
  interests         String[] // Array of interest tags
  goals             Goal[]   // What they're looking for

  // From registration (optional)
  bio               String?
  industry          String?
  companySize       CompanySize?
  yearsExperience   Int?
  skillsToOffer     String[]
  skillsNeeded      String[]

  // From enrichment agent (auto-populated)
  enrichmentStatus  EnrichmentStatus @default(PENDING)
  enrichedAt        DateTime?

  // Professional platforms
  linkedInHeadline  String?
  linkedInUrl       String?
  githubUsername    String?
  githubTopLanguages String[]
  githubRepoCount   Int?
  twitterHandle     String?
  twitterBio        String?

  // Content/Social platforms
  youtubeChannelUrl String?
  youtubeChannelName String?
  youtubeSubscriberRange String? // "1K-10K", "10K-100K", etc.
  instagramHandle   String?
  instagramBio      String?
  facebookProfileUrl String?

  // General
  personalWebsite   String?
  extractedSkills   String[]
  extractedInterests String[]
  enrichmentSources String[] // ["linkedin", "github", "twitter", "youtube", "instagram", "facebook"]

  // Relations
  user              UserReference @relation(fields: [userId], references: [id])

  createdAt         DateTime @default(now())
  updatedAt         DateTime @updatedAt

  @@index([userId])
}

enum Goal {
  LEARN
  NETWORK
  HIRE
  GET_HIRED
  FIND_PARTNERS
  FIND_INVESTORS
  SELL
  BUY
  MENTOR
  GET_MENTORED
}

enum CompanySize {
  SOLO
  STARTUP_1_10
  SMALL_11_50
  MEDIUM_51_200
  LARGE_201_1000
  ENTERPRISE_1000_PLUS
}

enum EnrichmentStatus {
  PENDING
  PROCESSING
  COMPLETED
  FAILED
  OPTED_OUT
}

model Recommendation {
  id              String   @id @default(cuid())
  userId          String
  eventId         String

  // Recommended user
  recommendedUserId String

  // LLM-generated content
  matchScore      Int      // 0-100
  reasons         String[] // Why they should connect
  conversationStarters String[]

  // Metadata
  generatedAt     DateTime @default(now())
  expiresAt       DateTime // Recommendations refresh daily

  // Tracking
  viewed          Boolean  @default(false)
  viewedAt        DateTime?
  pinged          Boolean  @default(false)
  pingedAt        DateTime?
  connected       Boolean  @default(false)
  connectedAt     DateTime?

  @@unique([userId, eventId, recommendedUserId])
  @@index([userId, eventId])
  @@index([eventId, expiresAt])
}
```

### 1.2 Registration Form Updates

**Required Fields (Step 1):**
```typescript
interface RegistrationRequired {
  firstName: string;
  lastName: string;
  email: string;
  company: string;
  role: string;
  interests: string[]; // Min 1, max 5, from predefined list
  goals: Goal[];       // Min 1, from predefined list
}
```

**Optional Fields (Step 2):**
```typescript
interface RegistrationOptional {
  bio?: string;              // Max 500 chars
  industry?: string;         // From predefined list
  companySize?: CompanySize;
  yearsExperience?: number;
  skillsToOffer?: string[];  // What can you help others with?
  skillsNeeded?: string[];   // What do you need help with?
  linkedInUrl?: string;      // Optional direct link
  githubUsername?: string;   // Optional direct link
  twitterHandle?: string;    // Optional direct link
}
```

**Enrichment Opt-in (Step 3):**
```typescript
interface EnrichmentConsent {
  allowEnrichment: boolean;
}
```

### 1.3 Enrichment Opt-In UI & Messaging

**Critical:** This step must clearly communicate VALUE without being pushy. The user should understand what they gain.

**UI Component: `profile-enrichment-step.tsx`**
```tsx
"use client";

import { useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import {
  Sparkles,
  Users,
  MessageSquare,
  Shield,
  Linkedin,
  Github,
  Twitter,
  Youtube,
  Instagram,
  Facebook,
} from "lucide-react";

interface EnrichmentStepProps {
  value: boolean;
  onChange: (value: boolean) => void;
}

export const EnrichmentStep = ({ value, onChange }: EnrichmentStepProps) => {
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="text-center space-y-2">
        <h2 className="text-2xl font-semibold">Supercharge Your Networking</h2>
        <p className="text-muted-foreground">
          This is completely optional, but can significantly improve your event experience
        </p>
      </div>

      {/* Main Toggle Card */}
      <Card className={value ? "border-primary" : ""}>
        <CardContent className="p-6">
          <div className="flex items-start justify-between gap-4">
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-2">
                <Sparkles className="h-5 w-5 text-amber-500" />
                <h3 className="font-semibold">Enable Smart Profile Matching</h3>
                <Badge variant="secondary">Recommended</Badge>
              </div>
              <p className="text-sm text-muted-foreground">
                Allow us to search for your public profiles to find better networking matches
              </p>
            </div>
            <Switch checked={value} onCheckedChange={onChange} />
          </div>
        </CardContent>
      </Card>

      {/* What We Search */}
      <div className="space-y-3">
        <h4 className="text-sm font-medium text-muted-foreground">
          Platforms we'll search (using your name & company):
        </h4>
        <div className="flex flex-wrap gap-2">
          <Badge variant="outline" className="gap-1">
            <Linkedin className="h-3 w-3" /> LinkedIn
          </Badge>
          <Badge variant="outline" className="gap-1">
            <Github className="h-3 w-3" /> GitHub
          </Badge>
          <Badge variant="outline" className="gap-1">
            <Twitter className="h-3 w-3" /> Twitter/X
          </Badge>
          <Badge variant="outline" className="gap-1">
            <Youtube className="h-3 w-3" /> YouTube
          </Badge>
          <Badge variant="outline" className="gap-1">
            <Instagram className="h-3 w-3" /> Instagram
          </Badge>
          <Badge variant="outline" className="gap-1">
            <Facebook className="h-3 w-3" /> Facebook
          </Badge>
        </div>
      </div>

      {/* Benefits */}
      <div className="grid gap-3">
        <h4 className="text-sm font-medium">What you get:</h4>

        <div className="flex items-start gap-3 p-3 rounded-lg bg-muted/50">
          <Users className="h-5 w-5 text-primary mt-0.5" />
          <div>
            <p className="font-medium text-sm">Better Match Recommendations</p>
            <p className="text-xs text-muted-foreground">
              We can suggest people who share your interests and goals
            </p>
          </div>
        </div>

        <div className="flex items-start gap-3 p-3 rounded-lg bg-muted/50">
          <MessageSquare className="h-5 w-5 text-primary mt-0.5" />
          <div>
            <p className="font-medium text-sm">Conversation Starters</p>
            <p className="text-xs text-muted-foreground">
              Know what to talk about before you even say hello
            </p>
          </div>
        </div>

        <div className="flex items-start gap-3 p-3 rounded-lg bg-muted/50">
          <Sparkles className="h-5 w-5 text-primary mt-0.5" />
          <div>
            <p className="font-medium text-sm">Context for Others</p>
            <p className="text-xs text-muted-foreground">
              Other attendees can see why connecting with YOU would be valuable
            </p>
          </div>
        </div>
      </div>

      {/* Privacy Assurance */}
      <div className="flex items-start gap-3 p-4 rounded-lg border bg-background">
        <Shield className="h-5 w-5 text-green-600 mt-0.5" />
        <div>
          <p className="font-medium text-sm">Your Privacy is Protected</p>
          <ul className="text-xs text-muted-foreground mt-1 space-y-1">
            <li>• We only look at publicly available information</li>
            <li>• We never access private accounts or DMs</li>
            <li>• We don't store passwords or login to anything</li>
            <li>• You can delete this data anytime from settings</li>
          </ul>
        </div>
      </div>

      {/* Skip Option */}
      {!value && (
        <p className="text-center text-sm text-muted-foreground">
          You can always enable this later in your profile settings
        </p>
      )}
    </div>
  );
};
```

**Key Messaging Principles:**
1. **Lead with value, not permission** - "Supercharge Your Networking" vs "Can we access your data?"
2. **Make it clearly optional** - "This is completely optional"
3. **Show specific benefits** - Not vague "better experience" but concrete outcomes
4. **Address privacy concerns proactively** - Shield icon, bullet points about what we DON'T do
5. **Low-pressure skip** - "You can always enable this later"

### 1.3 Frontend: Registration Flow

Create `globalconnect/src/app/(auth)/register/steps/`:

```
steps/
├── basic-info.tsx      # Name, email, company, role
├── interests-goals.tsx # Interests picker, goals multi-select
├── optional-details.tsx # Bio, industry, skills
└── profile-enrichment.tsx # Opt-in for auto-enrichment
```

**Interest Categories:**
```typescript
const INTEREST_CATEGORIES = {
  "Technology": [
    "AI/ML", "Web Development", "Mobile", "Cloud/DevOps",
    "Blockchain", "Cybersecurity", "Data Science", "IoT"
  ],
  "Business": [
    "Startups", "Enterprise", "SaaS", "E-commerce",
    "Fintech", "HealthTech", "EdTech", "MarTech"
  ],
  "Role-Based": [
    "Engineering", "Product", "Design", "Marketing",
    "Sales", "Operations", "Leadership", "Investing"
  ],
  "Personal": [
    "Career Growth", "Mentorship", "Speaking", "Writing",
    "Open Source", "Community Building"
  ]
};
```

**Goal Options:**
```typescript
const GOALS = [
  { value: "LEARN", label: "Learn new skills/knowledge", icon: BookOpen },
  { value: "NETWORK", label: "Expand my network", icon: Users },
  { value: "HIRE", label: "Find talent to hire", icon: UserPlus },
  { value: "GET_HIRED", label: "Find job opportunities", icon: Briefcase },
  { value: "FIND_PARTNERS", label: "Find business partners", icon: Handshake },
  { value: "FIND_INVESTORS", label: "Meet investors", icon: TrendingUp },
  { value: "SELL", label: "Find customers/clients", icon: ShoppingBag },
  { value: "BUY", label: "Find solutions/vendors", icon: Search },
  { value: "MENTOR", label: "Mentor others", icon: GraduationCap },
  { value: "GET_MENTORED", label: "Find a mentor", icon: Compass },
];
```

---

## Phase 2: Profile Enrichment Agent

### 2.1 Agent Architecture (LangGraph)

Create `oracle-ai-service/app/agents/profile_enrichment/`:

```
profile_enrichment/
├── __init__.py
├── agent.py           # Main LangGraph agent
├── nodes/
│   ├── search.py      # Tavily search node
│   ├── extract.py     # Profile extraction node
│   ├── validate.py    # Validation node
│   └── store.py       # Database storage node
├── tools/
│   ├── tavily_search.py
│   ├── github_api.py  # Public API, no auth needed
│   └── web_reader.py
└── prompts/
    └── extraction_prompts.py
```

### 2.2 Agent Implementation

**agent.py:**
```python
from langgraph.graph import StateGraph, END
from typing import TypedDict, List, Optional
import asyncio

class EnrichmentState(TypedDict):
    # Input
    user_id: str
    name: str
    email: str
    company: str
    role: str

    # Search results
    search_results: List[dict]

    # Extracted profiles
    linkedin_data: Optional[dict]
    github_data: Optional[dict]
    twitter_data: Optional[dict]
    youtube_data: Optional[dict]
    instagram_data: Optional[dict]
    facebook_data: Optional[dict]
    web_data: Optional[dict]

    # Final output
    enriched_profile: Optional[dict]
    status: str
    error: Optional[str]

def create_enrichment_agent():
    workflow = StateGraph(EnrichmentState)

    # Add nodes
    workflow.add_node("search_profiles", search_profiles_node)
    workflow.add_node("extract_linkedin", extract_linkedin_node)
    workflow.add_node("extract_github", extract_github_node)
    workflow.add_node("extract_twitter", extract_twitter_node)
    workflow.add_node("extract_youtube", extract_youtube_node)
    workflow.add_node("extract_instagram", extract_instagram_node)
    workflow.add_node("extract_facebook", extract_facebook_node)
    workflow.add_node("merge_and_validate", merge_and_validate_node)
    workflow.add_node("store_results", store_results_node)

    # Define edges - PARALLEL extraction from all platforms
    # After search, fan out to all extractors in parallel
    workflow.set_entry_point("search_profiles")

    # Parallel extraction: search fans out to all extractors
    workflow.add_edge("search_profiles", "parallel_extract")

    # Add parallel extraction node that uses asyncio.gather()
    workflow.add_node("parallel_extract", parallel_extract_all_platforms)

    # After parallel extraction completes, merge results
    workflow.add_edge("parallel_extract", "merge_and_validate")
    workflow.add_edge("merge_and_validate", "store_results")
    workflow.add_edge("store_results", END)

    return workflow.compile()


async def parallel_extract_all_platforms(state: EnrichmentState) -> EnrichmentState:
    """
    Execute all platform extractions in parallel using asyncio.gather().
    This reduces total enrichment time from ~30s (sequential) to ~5-8s (parallel).
    """
    import asyncio

    # Run all extractions concurrently
    results = await asyncio.gather(
        extract_linkedin_node(state.copy()),
        extract_github_node(state.copy()),
        extract_twitter_node(state.copy()),
        extract_youtube_node(state.copy()),
        extract_instagram_node(state.copy()),
        extract_facebook_node(state.copy()),
        return_exceptions=True  # Don't fail if one platform fails
    )

    # Merge results back into state
    platform_keys = [
        "linkedin_data", "github_data", "twitter_data",
        "youtube_data", "instagram_data", "facebook_data"
    ]

    for i, result in enumerate(results):
        if isinstance(result, Exception):
            # Log error but continue with other platforms
            logger.warning(f"Extraction failed for {platform_keys[i]}: {result}")
            state[platform_keys[i]] = None
        else:
            state[platform_keys[i]] = result.get(platform_keys[i])

    return state

async def search_profiles_node(state: EnrichmentState) -> EnrichmentState:
    """Search for user's public profiles across platforms."""
    from tavily import TavilyClient

    client = TavilyClient(api_key=settings.TAVILY_API_KEY)

    # Build search query
    search_query = f"{state['name']} {state['company']} {state['role']}"

    # Search for profiles across all platforms
    results = await client.search(
        query=search_query,
        search_depth="advanced",
        include_domains=[
            "linkedin.com",
            "github.com",
            "twitter.com",
            "x.com",
            "youtube.com",
            "instagram.com",
            "facebook.com",
            "medium.com",
            "dev.to"
        ],
        max_results=15  # Increased to cover more platforms
    )

    state["search_results"] = results.get("results", [])
    return state

async def extract_linkedin_node(state: EnrichmentState) -> EnrichmentState:
    """Extract LinkedIn profile data."""
    linkedin_results = [
        r for r in state["search_results"]
        if "linkedin.com/in/" in r.get("url", "")
    ]

    if not linkedin_results:
        state["linkedin_data"] = None
        return state

    # Use LLM to extract structured data from search snippet
    profile_url = linkedin_results[0]["url"]
    snippet = linkedin_results[0].get("content", "")

    extraction_prompt = f"""
    Extract professional information from this LinkedIn search result:

    URL: {profile_url}
    Snippet: {snippet}

    Return JSON:
    {{
        "url": "...",
        "headline": "...",
        "inferred_seniority": "junior|mid|senior|executive",
        "inferred_function": "engineering|product|design|sales|marketing|other"
    }}

    Only include fields you can confidently extract. Use null for uncertain fields.
    """

    extracted = await llm.generate(extraction_prompt, response_format="json")
    state["linkedin_data"] = extracted
    return state

async def extract_github_node(state: EnrichmentState) -> EnrichmentState:
    """Extract GitHub profile data using public API."""
    github_results = [
        r for r in state["search_results"]
        if "github.com/" in r.get("url", "") and "/repos" not in r.get("url", "")
    ]

    if not github_results:
        state["github_data"] = None
        return state

    # Extract username from URL
    url = github_results[0]["url"]
    username = url.split("github.com/")[-1].split("/")[0].split("?")[0]

    # Call GitHub public API (no auth needed for public profiles)
    async with httpx.AsyncClient() as client:
        # Get user profile
        user_resp = await client.get(f"https://api.github.com/users/{username}")
        if user_resp.status_code != 200:
            state["github_data"] = None
            return state

        user_data = user_resp.json()

        # Get top repositories
        repos_resp = await client.get(
            f"https://api.github.com/users/{username}/repos",
            params={"sort": "updated", "per_page": 10}
        )
        repos = repos_resp.json() if repos_resp.status_code == 200 else []

        # Extract languages from repos
        languages = {}
        for repo in repos:
            if repo.get("language"):
                lang = repo["language"]
                languages[lang] = languages.get(lang, 0) + 1

        top_languages = sorted(languages.keys(), key=lambda x: languages[x], reverse=True)[:5]

        state["github_data"] = {
            "username": username,
            "url": f"https://github.com/{username}",
            "bio": user_data.get("bio"),
            "public_repos": user_data.get("public_repos", 0),
            "followers": user_data.get("followers", 0),
            "top_languages": top_languages,
            "recent_activity": [repo["name"] for repo in repos[:5]]
        }

    return state

async def extract_twitter_node(state: EnrichmentState) -> EnrichmentState:
    """Extract Twitter/X profile data from search results."""
    twitter_results = [
        r for r in state["search_results"]
        if "twitter.com/" in r.get("url", "") or "x.com/" in r.get("url", "")
    ]

    if not twitter_results:
        state["twitter_data"] = None
        return state

    # Extract from search snippet (can't access Twitter API without auth)
    url = twitter_results[0]["url"]
    snippet = twitter_results[0].get("content", "")

    # Use LLM to extract what we can from the snippet
    extraction_prompt = f"""
    Extract Twitter profile information from this search result:

    URL: {url}
    Snippet: {snippet}

    Return JSON:
    {{
        "url": "...",
        "handle": "@...",
        "bio_snippet": "...",
        "inferred_interests": ["..."]
    }}
    """

    extracted = await llm.generate(extraction_prompt, response_format="json")
    state["twitter_data"] = extracted
    return state

async def extract_youtube_node(state: EnrichmentState) -> EnrichmentState:
    """Extract YouTube channel data from search results."""
    youtube_results = [
        r for r in state["search_results"]
        if "youtube.com/" in r.get("url", "") and (
            "/channel/" in r.get("url", "") or
            "/@" in r.get("url", "") or
            "/c/" in r.get("url", "")
        )
    ]

    if not youtube_results:
        state["youtube_data"] = None
        return state

    url = youtube_results[0]["url"]
    snippet = youtube_results[0].get("content", "")

    extraction_prompt = f"""
    Extract YouTube channel information from this search result:

    URL: {url}
    Snippet: {snippet}

    Return JSON:
    {{
        "url": "...",
        "channel_name": "...",
        "subscriber_range": "Under 1K|1K-10K|10K-100K|100K-1M|1M+",
        "content_focus": ["tech", "business", "education", etc.],
        "is_content_creator": true/false
    }}

    Use null for fields you cannot determine.
    """

    extracted = await llm.generate(extraction_prompt, response_format="json")
    state["youtube_data"] = extracted
    return state

async def extract_instagram_node(state: EnrichmentState) -> EnrichmentState:
    """Extract Instagram profile data from search results."""
    instagram_results = [
        r for r in state["search_results"]
        if "instagram.com/" in r.get("url", "")
    ]

    if not instagram_results:
        state["instagram_data"] = None
        return state

    url = instagram_results[0]["url"]
    snippet = instagram_results[0].get("content", "")

    # Extract handle from URL
    handle = url.split("instagram.com/")[-1].split("/")[0].split("?")[0]

    extraction_prompt = f"""
    Extract Instagram profile information from this search result:

    URL: {url}
    Handle: @{handle}
    Snippet: {snippet}

    Return JSON:
    {{
        "url": "...",
        "handle": "@...",
        "bio_snippet": "...",
        "is_business_account": true/false,
        "content_themes": ["..."]
    }}
    """

    extracted = await llm.generate(extraction_prompt, response_format="json")
    state["instagram_data"] = extracted
    return state

async def extract_facebook_node(state: EnrichmentState) -> EnrichmentState:
    """Extract Facebook profile data from search results."""
    facebook_results = [
        r for r in state["search_results"]
        if "facebook.com/" in r.get("url", "")
    ]

    if not facebook_results:
        state["facebook_data"] = None
        return state

    url = facebook_results[0]["url"]
    snippet = facebook_results[0].get("content", "")

    extraction_prompt = f"""
    Extract Facebook profile/page information from this search result:

    URL: {url}
    Snippet: {snippet}

    Return JSON:
    {{
        "url": "...",
        "profile_type": "personal|business_page|public_figure",
        "name_or_page_title": "...",
        "bio_snippet": "..."
    }}

    Use null for fields you cannot determine.
    """

    extracted = await llm.generate(extraction_prompt, response_format="json")
    state["facebook_data"] = extracted
    return state

async def merge_and_validate_node(state: EnrichmentState) -> EnrichmentState:
    """Merge all extracted data and validate consistency."""

    # Combine all sources
    enriched = {
        "sources": [],
        # Professional
        "linkedin_url": None,
        "linkedin_headline": None,
        "github_username": None,
        "github_top_languages": [],
        "github_repo_count": 0,
        "twitter_handle": None,
        "twitter_bio": None,
        # Content/Social
        "youtube_channel_url": None,
        "youtube_channel_name": None,
        "youtube_subscriber_range": None,
        "instagram_handle": None,
        "instagram_bio": None,
        "facebook_profile_url": None,
        # Extracted
        "extracted_skills": [],
        "extracted_interests": [],
        "inferred_seniority": None,
        "inferred_function": None,
        "is_content_creator": False,
    }

    if state.get("linkedin_data"):
        enriched["sources"].append("linkedin")
        enriched["linkedin_url"] = state["linkedin_data"].get("url")
        enriched["linkedin_headline"] = state["linkedin_data"].get("headline")
        enriched["inferred_seniority"] = state["linkedin_data"].get("inferred_seniority")
        enriched["inferred_function"] = state["linkedin_data"].get("inferred_function")

    if state.get("github_data"):
        enriched["sources"].append("github")
        enriched["github_username"] = state["github_data"].get("username")
        enriched["github_top_languages"] = state["github_data"].get("top_languages", [])
        enriched["github_repo_count"] = state["github_data"].get("public_repos", 0)
        enriched["extracted_skills"].extend(state["github_data"].get("top_languages", []))

    if state.get("twitter_data"):
        enriched["sources"].append("twitter")
        enriched["twitter_handle"] = state["twitter_data"].get("handle")
        enriched["twitter_bio"] = state["twitter_data"].get("bio_snippet")
        enriched["extracted_interests"].extend(
            state["twitter_data"].get("inferred_interests", [])
        )

    if state.get("youtube_data"):
        enriched["sources"].append("youtube")
        enriched["youtube_channel_url"] = state["youtube_data"].get("url")
        enriched["youtube_channel_name"] = state["youtube_data"].get("channel_name")
        enriched["youtube_subscriber_range"] = state["youtube_data"].get("subscriber_range")
        if state["youtube_data"].get("is_content_creator"):
            enriched["is_content_creator"] = True
        enriched["extracted_interests"].extend(
            state["youtube_data"].get("content_focus", [])
        )

    if state.get("instagram_data"):
        enriched["sources"].append("instagram")
        enriched["instagram_handle"] = state["instagram_data"].get("handle")
        enriched["instagram_bio"] = state["instagram_data"].get("bio_snippet")
        enriched["extracted_interests"].extend(
            state["instagram_data"].get("content_themes", [])
        )

    if state.get("facebook_data"):
        enriched["sources"].append("facebook")
        enriched["facebook_profile_url"] = state["facebook_data"].get("url")

    # Deduplicate
    enriched["extracted_skills"] = list(set(enriched["extracted_skills"]))
    enriched["extracted_interests"] = list(set(enriched["extracted_interests"]))

    state["enriched_profile"] = enriched
    state["status"] = "completed" if enriched["sources"] else "no_data_found"
    return state

async def store_results_node(state: EnrichmentState) -> EnrichmentState:
    """Store enriched profile in database."""
    if state["status"] != "completed":
        return state

    enriched = state["enriched_profile"]

    await prisma.userprofile.update(
        where={"userId": state["user_id"]},
        data={
            "enrichmentStatus": "COMPLETED",
            "enrichedAt": datetime.utcnow(),
            # Professional platforms
            "linkedInUrl": enriched.get("linkedin_url"),
            "linkedInHeadline": enriched.get("linkedin_headline"),
            "githubUsername": enriched.get("github_username"),
            "githubTopLanguages": enriched.get("github_top_languages", []),
            "githubRepoCount": enriched.get("github_repo_count", 0),
            "twitterHandle": enriched.get("twitter_handle"),
            "twitterBio": enriched.get("twitter_bio"),
            # Content/Social platforms
            "youtubeChannelUrl": enriched.get("youtube_channel_url"),
            "youtubeChannelName": enriched.get("youtube_channel_name"),
            "youtubeSubscriberRange": enriched.get("youtube_subscriber_range"),
            "instagramHandle": enriched.get("instagram_handle"),
            "instagramBio": enriched.get("instagram_bio"),
            "facebookProfileUrl": enriched.get("facebook_profile_url"),
            # Extracted data
            "extractedSkills": enriched.get("extracted_skills", []),
            "extractedInterests": enriched.get("extracted_interests", []),
            "enrichmentSources": enriched.get("sources", []),
        }
    )

    return state
```

### 2.3 Enrichment API Endpoint

**oracle-ai-service/app/features/enrichment/router.py:**
```python
from fastapi import APIRouter, BackgroundTasks

router = APIRouter(prefix="/enrichment", tags=["Profile Enrichment"])

@router.post("/enrich/{user_id}")
async def enrich_user_profile(
    user_id: str,
    background_tasks: BackgroundTasks
):
    """Trigger profile enrichment for a user."""
    # Get user's registration data
    user = await get_user_with_profile(user_id)

    if not user:
        raise HTTPException(404, "User not found")

    if user.profile.enrichmentStatus == "COMPLETED":
        return {"status": "already_enriched", "data": user.profile}

    if user.profile.enrichmentStatus == "OPTED_OUT":
        return {"status": "opted_out"}

    # Run enrichment in background
    background_tasks.add_task(
        run_enrichment_agent,
        user_id=user_id,
        name=f"{user.firstName} {user.lastName}",
        email=user.email,
        company=user.company,
        role=user.role
    )

    return {"status": "processing", "message": "Enrichment started"}

@router.get("/status/{user_id}")
async def get_enrichment_status(user_id: str):
    """Check enrichment status for a user."""
    profile = await get_user_profile(user_id)

    return {
        "status": profile.enrichmentStatus,
        "enrichedAt": profile.enrichedAt,
        "sources": profile.enrichmentSources,
    }
```

---

## Phase 3: LLM Recommendation Engine

### 3.1 Recommendation Service

Create `oracle-ai-service/app/features/recommendations/matchmaking.py`:

```python
from datetime import datetime, timedelta
from typing import List
import json

class MatchmakingService:
    def __init__(self, llm_client, prisma_client):
        self.llm = llm_client
        self.prisma = prisma_client

    async def generate_recommendations(
        self,
        user_id: str,
        event_id: str,
        force_refresh: bool = False
    ) -> List[dict]:
        """Generate personalized recommendations for a user at an event."""

        # Check for cached recommendations
        if not force_refresh:
            cached = await self._get_cached_recommendations(user_id, event_id)
            if cached:
                return cached

        # Get the user's full profile
        user = await self._get_enriched_user(user_id)

        # Get all other attendees at the event
        attendees = await self._get_event_attendees(event_id, exclude_user=user_id)

        if not attendees:
            return []

        # Build the prompt
        prompt = self._build_recommendation_prompt(user, attendees)

        # Call LLM
        response = await self.llm.generate(
            prompt,
            model="claude-sonnet-4-20250514",  # Good balance of quality/cost
            max_tokens=4000,
            response_format="json"
        )

        recommendations = json.loads(response)

        # Store recommendations
        await self._store_recommendations(user_id, event_id, recommendations)

        return recommendations

    def _build_recommendation_prompt(self, user: dict, attendees: List[dict]) -> str:
        return f"""You are an expert networking matchmaker for professional events. Your job is to identify the most valuable connections for an attendee.

## The Attendee Seeking Recommendations

**Name:** {user['name']}
**Role:** {user['role']} at {user['company']}
**Industry:** {user.get('industry', 'Not specified')}
**Goals at this event:** {', '.join(user.get('goals', ['Networking']))}
**Interests:** {', '.join(user.get('interests', []))}
**Skills to offer:** {', '.join(user.get('skillsToOffer', []))}
**Looking for help with:** {', '.join(user.get('skillsNeeded', []))}
**Bio:** {user.get('bio', 'No bio provided')}

### Enriched Profile Data (from public sources):
- LinkedIn Headline: {user.get('linkedInHeadline', 'N/A')}
- GitHub Languages: {', '.join(user.get('githubTopLanguages', [])) or 'N/A'}
- GitHub Repos: {user.get('githubRepoCount', 'N/A')}
- Extracted Skills: {', '.join(user.get('extractedSkills', [])) or 'N/A'}

---

## Other Attendees at This Event

{self._format_attendees(attendees)}

---

## Your Task

Analyze all attendees and select the TOP 10 people this attendee should meet.

For each recommendation, consider:
1. **Goal Alignment** - Do their goals complement each other? (e.g., one hiring + one job seeking)
2. **Interest Overlap** - Shared interests for conversation
3. **Skill Exchange** - Can they help each other?
4. **Industry Relevance** - Same or adjacent industries
5. **Seniority Fit** - Appropriate for their career stage
6. **Unique Value** - What specific value can this connection bring?

## Response Format

Return a JSON array with exactly 10 recommendations, ranked by value:

```json
[
  {{
    "userId": "user_id_here",
    "matchScore": 92,
    "reasons": [
      "She's hiring engineers and you're looking for opportunities",
      "Both passionate about AI/ML applications in fintech",
      "Her 10+ years at Stripe could provide valuable mentorship"
    ],
    "conversationStarters": [
      "I noticed you're building the payments infrastructure team - I'd love to hear about the technical challenges you're solving",
      "What's your take on the recent AI developments in fraud detection?"
    ],
    "potentialValue": "Career opportunity + Industry insights"
  }},
  ...
]
```

Important:
- matchScore should be 0-100 based on connection value
- Provide 2-3 specific reasons (not generic)
- Conversation starters should reference specific details
- potentialValue should be a short summary of what they could gain

Return ONLY the JSON array, no other text.
"""

    def _format_attendees(self, attendees: List[dict]) -> str:
        formatted = []
        for i, a in enumerate(attendees, 1):
            formatted.append(f"""
### Attendee {i}: {a['name']}
- **ID:** {a['id']}
- **Role:** {a['role']} at {a['company']}
- **Goals:** {', '.join(a.get('goals', []))}
- **Interests:** {', '.join(a.get('interests', []))}
- **Skills to Offer:** {', '.join(a.get('skillsToOffer', [])) or 'Not specified'}
- **Looking For:** {', '.join(a.get('skillsNeeded', [])) or 'Not specified'}
- **LinkedIn:** {a.get('linkedInHeadline', 'N/A')}
- **GitHub Languages:** {', '.join(a.get('githubTopLanguages', [])) or 'N/A'}
""")
        return "\n".join(formatted)

    async def _store_recommendations(
        self,
        user_id: str,
        event_id: str,
        recommendations: List[dict]
    ):
        """Store recommendations in database with expiration."""
        expires_at = datetime.utcnow() + timedelta(hours=24)

        # Delete old recommendations
        await self.prisma.recommendation.delete_many(
            where={"userId": user_id, "eventId": event_id}
        )

        # Insert new ones
        for rec in recommendations:
            await self.prisma.recommendation.create(
                data={
                    "userId": user_id,
                    "eventId": event_id,
                    "recommendedUserId": rec["userId"],
                    "matchScore": rec["matchScore"],
                    "reasons": rec["reasons"],
                    "conversationStarters": rec["conversationStarters"],
                    "expiresAt": expires_at,
                }
            )

    async def _get_cached_recommendations(
        self,
        user_id: str,
        event_id: str
    ) -> List[dict] | None:
        """Get cached recommendations if still valid."""
        recs = await self.prisma.recommendation.find_many(
            where={
                "userId": user_id,
                "eventId": event_id,
                "expiresAt": {"gt": datetime.utcnow()}
            },
            order_by={"matchScore": "desc"}
        )

        if not recs:
            return None

        return [
            {
                "userId": r.recommendedUserId,
                "matchScore": r.matchScore,
                "reasons": r.reasons,
                "conversationStarters": r.conversationStarters,
            }
            for r in recs
        ]
```

### 3.2 Recommendation API

**oracle-ai-service/app/features/recommendations/router.py:**
```python
from fastapi import APIRouter, BackgroundTasks

router = APIRouter(prefix="/recommendations", tags=["Matchmaking"])

@router.get("/{event_id}/for/{user_id}")
async def get_recommendations(
    event_id: str,
    user_id: str,
    refresh: bool = False
):
    """Get personalized recommendations for a user at an event."""
    service = MatchmakingService(llm_client, prisma)

    recommendations = await service.generate_recommendations(
        user_id=user_id,
        event_id=event_id,
        force_refresh=refresh
    )

    # Enrich with user details for display
    enriched = []
    for rec in recommendations:
        user = await get_user_display_info(rec["userId"])
        enriched.append({
            **rec,
            "user": user
        })

    return {"recommendations": enriched}

@router.post("/{event_id}/generate-all")
async def generate_all_recommendations(
    event_id: str,
    background_tasks: BackgroundTasks
):
    """Generate recommendations for all attendees at an event (admin endpoint)."""
    attendees = await get_event_attendees(event_id)

    for attendee in attendees:
        background_tasks.add_task(
            generate_user_recommendations,
            user_id=attendee.id,
            event_id=event_id
        )

    return {
        "status": "processing",
        "message": f"Generating recommendations for {len(attendees)} attendees"
    }

@router.post("/{event_id}/recommendations/{recommendation_id}/viewed")
async def mark_recommendation_viewed(
    event_id: str,
    recommendation_id: str
):
    """Track when a recommendation is viewed."""
    await prisma.recommendation.update(
        where={"id": recommendation_id},
        data={"viewed": True, "viewedAt": datetime.utcnow()}
    )
    return {"success": True}

@router.post("/{event_id}/recommendations/{recommendation_id}/pinged")
async def mark_recommendation_pinged(
    event_id: str,
    recommendation_id: str
):
    """Track when a recommended user is pinged."""
    await prisma.recommendation.update(
        where={"id": recommendation_id},
        data={"pinged": True, "pingedAt": datetime.utcnow()}
    )
    return {"success": True}
```

### 3.3 Large Event Handling (500+ Attendees)

For events with large numbers of attendees, we must pre-filter candidates before sending to the LLM to avoid token limit issues and reduce costs.

**Pre-filtering Strategy:**

```python
# oracle-ai-service/app/features/recommendations/prefilter.py

from typing import List, Set
from app.models import UserProfile, EventAttendee

class CandidatePreFilter:
    """
    Pre-filters recommendation candidates for large events.
    Reduces candidate pool before LLM processing to handle token limits.
    """

    # Maximum candidates to send to LLM per request
    MAX_LLM_CANDIDATES = 50

    # Batch size for very large events
    BATCH_SIZE = 100

    async def prefilter_candidates(
        self,
        user: UserProfile,
        all_attendees: List[EventAttendee],
        event_id: str
    ) -> List[EventAttendee]:
        """
        Apply heuristic filters before LLM scoring.
        For events with 500+ attendees, this is REQUIRED.
        """
        event_size = len(all_attendees)

        if event_size < 100:
            # Small event: no pre-filtering needed
            return all_attendees[:self.MAX_LLM_CANDIDATES]

        # Step 1: Exclude self and already-connected users
        candidates = await self._exclude_existing_connections(user.id, all_attendees)

        # Step 2: Goal-based pre-filtering (highest priority)
        candidates = self._filter_by_goal_compatibility(user, candidates)

        # Step 3: Interest overlap scoring (lightweight, no LLM)
        candidates = self._score_by_interest_overlap(user, candidates)

        # Step 4: Seniority/role matching heuristics
        candidates = self._apply_seniority_heuristics(user, candidates)

        # Return top candidates for LLM scoring
        return candidates[:self.MAX_LLM_CANDIDATES]

    async def _exclude_existing_connections(
        self,
        user_id: str,
        attendees: List[EventAttendee]
    ) -> List[EventAttendee]:
        """Remove users already in the user's network."""
        existing_connections = await self._get_existing_connection_ids(user_id)
        return [a for a in attendees if a.user_id not in existing_connections and a.user_id != user_id]

    def _filter_by_goal_compatibility(
        self,
        user: UserProfile,
        candidates: List[EventAttendee]
    ) -> List[EventAttendee]:
        """
        Goal-based pre-filtering. These pairs are complementary:
        - HIRE <-> GET_HIRED
        - FIND_INVESTORS <-> INVEST (future)
        - MENTOR <-> GET_MENTORED
        - SELL <-> BUY
        - FIND_PARTNERS <-> FIND_PARTNERS
        """
        goal_compatibility = {
            "HIRE": {"GET_HIRED"},
            "GET_HIRED": {"HIRE"},
            "MENTOR": {"GET_MENTORED"},
            "GET_MENTORED": {"MENTOR"},
            "SELL": {"BUY"},
            "BUY": {"SELL"},
            "FIND_PARTNERS": {"FIND_PARTNERS"},
            "FIND_INVESTORS": {"FIND_INVESTORS", "NETWORK"},
            "LEARN": {"MENTOR", "NETWORK"},
            "NETWORK": {"NETWORK", "LEARN", "FIND_PARTNERS"},
        }

        user_goal = user.goal
        compatible_goals = goal_compatibility.get(user_goal, set())

        # Include NETWORK as a universal fallback
        compatible_goals.add("NETWORK")

        # Primary: Users with directly compatible goals
        primary = [c for c in candidates if c.user_profile.goal in compatible_goals]

        # Secondary: Others (sorted by interest overlap later)
        secondary = [c for c in candidates if c.user_profile.goal not in compatible_goals]

        # Prioritize goal-compatible candidates
        return primary + secondary

    def _score_by_interest_overlap(
        self,
        user: UserProfile,
        candidates: List[EventAttendee]
    ) -> List[EventAttendee]:
        """
        Lightweight interest overlap scoring (no LLM needed).
        Uses Jaccard similarity for fast set intersection.
        """
        user_interests = set(user.interests or [])

        if not user_interests:
            return candidates

        scored = []
        for candidate in candidates:
            candidate_interests = set(candidate.user_profile.interests or [])

            if candidate_interests:
                # Jaccard similarity: |A ∩ B| / |A ∪ B|
                intersection = len(user_interests & candidate_interests)
                union = len(user_interests | candidate_interests)
                score = intersection / union if union > 0 else 0
            else:
                score = 0

            scored.append((candidate, score))

        # Sort by score descending
        scored.sort(key=lambda x: x[1], reverse=True)
        return [c for c, _ in scored]

    def _apply_seniority_heuristics(
        self,
        user: UserProfile,
        candidates: List[EventAttendee]
    ) -> List[EventAttendee]:
        """
        Apply seniority-based heuristics for HIRE/GET_HIRED goals.
        Mentors should match with more junior people, etc.
        """
        if user.goal == "MENTOR":
            # Mentors should match with junior/mid-level
            preferred_seniority = ["junior", "mid"]
            return self._reorder_by_seniority(candidates, preferred_seniority) + \
                   [c for c in candidates if c.user_profile.seniority not in preferred_seniority]

        if user.goal == "GET_MENTORED":
            # Mentees should match with senior/executive
            preferred_seniority = ["senior", "executive"]
            return self._reorder_by_seniority(candidates, preferred_seniority) + \
                   [c for c in candidates if c.user_profile.seniority not in preferred_seniority]

        return candidates

    def _reorder_by_seniority(
        self,
        candidates: List[EventAttendee],
        preferred: List[str]
    ) -> List[EventAttendee]:
        return [c for c in candidates if c.user_profile.seniority in preferred]

    async def _get_existing_connection_ids(self, user_id: str) -> Set[str]:
        """Fetch IDs of users already connected to this user."""
        connections = await prisma.connection.find_many(
            where={"userId": user_id}
        )
        return {c.connectedUserId for c in connections}


class BatchedRecommendationEngine:
    """
    Handles recommendation generation for very large events (1000+).
    Processes candidates in batches to manage memory and API limits.
    """

    BATCH_SIZE = 50
    MAX_TOTAL_RECOMMENDATIONS = 10

    async def generate_batched_recommendations(
        self,
        user_id: str,
        event_id: str,
        prefiltered_candidates: List[EventAttendee]
    ) -> List[dict]:
        """
        Process candidates in batches for very large candidate pools.
        Uses progressive filtering: first batch may yield enough results.
        """
        all_scored = []

        for i in range(0, len(prefiltered_candidates), self.BATCH_SIZE):
            batch = prefiltered_candidates[i:i + self.BATCH_SIZE]

            # Score this batch with LLM
            batch_scores = await self._score_batch_with_llm(user_id, batch)
            all_scored.extend(batch_scores)

            # Early exit: if we have enough high-quality matches
            high_quality = [s for s in all_scored if s["score"] >= 0.8]
            if len(high_quality) >= self.MAX_TOTAL_RECOMMENDATIONS:
                break

        # Sort all scored candidates and return top N
        all_scored.sort(key=lambda x: x["score"], reverse=True)
        return all_scored[:self.MAX_TOTAL_RECOMMENDATIONS]

    async def _score_batch_with_llm(
        self,
        user_id: str,
        batch: List[EventAttendee]
    ) -> List[dict]:
        """Score a batch of candidates using LLM."""
        # Implementation uses the existing RecommendationEngine._call_llm_for_matches
        # but operates on a smaller, pre-filtered batch
        pass
```

**Integration with Recommendation API:**

```python
# Update in oracle-ai-service/app/features/recommendations/engine.py

async def generate_recommendations(
    self,
    user_id: str,
    event_id: str,
    limit: int = 5
) -> List[RecommendationResult]:
    """Generate recommendations with large event support."""

    # Get all attendees
    all_attendees = await self._get_event_attendees(event_id)
    event_size = len(all_attendees)

    # Log event size for monitoring
    logger.info(f"Generating recommendations for event {event_id} with {event_size} attendees")

    # For large events, pre-filter candidates
    if event_size >= 100:
        prefilter = CandidatePreFilter()
        candidates = await prefilter.prefilter_candidates(
            user=await self._get_user_profile(user_id),
            all_attendees=all_attendees,
            event_id=event_id
        )
        logger.info(f"Pre-filtered to {len(candidates)} candidates")
    else:
        candidates = all_attendees

    # For very large events (1000+), use batched processing
    if event_size >= 1000:
        engine = BatchedRecommendationEngine()
        return await engine.generate_batched_recommendations(
            user_id=user_id,
            event_id=event_id,
            prefiltered_candidates=candidates
        )

    # Standard LLM-based matching for filtered candidates
    return await self._generate_llm_recommendations(user_id, candidates, limit)
```

---

## Phase 4: Frontend Integration

### 4.1 Recommendations Tab Component

Create `globalconnect/src/components/features/networking/recommendations-panel.tsx`:

```tsx
"use client";

import { useState } from "react";
import { useRecommendations } from "@/hooks/use-recommendations";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Sparkles,
  MessageCircle,
  ChevronDown,
  ChevronUp,
  RefreshCw,
  Github,
  Linkedin,
  Twitter,
} from "lucide-react";

interface RecommendationsPanelProps {
  eventId: string;
  onPing: (userId: string, message?: string) => void;
  onStartChat: (userId: string, userName: string) => void;
}

export const RecommendationsPanel = ({
  eventId,
  onPing,
  onStartChat,
}: RecommendationsPanelProps) => {
  const { recommendations, isLoading, refresh, isRefreshing } = useRecommendations(eventId);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  if (isLoading) {
    return <RecommendationsSkeleton />;
  }

  if (!recommendations.length) {
    return (
      <div className="flex flex-col items-center justify-center p-8 text-center">
        <Sparkles className="h-12 w-12 text-muted-foreground mb-4" />
        <h3 className="font-semibold text-lg">No Recommendations Yet</h3>
        <p className="text-sm text-muted-foreground mt-1">
          Check back soon - we're finding the best connections for you.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between px-2">
        <div className="flex items-center gap-2">
          <Sparkles className="h-5 w-5 text-amber-500" />
          <h3 className="font-semibold">Recommended for You</h3>
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={refresh}
          disabled={isRefreshing}
        >
          <RefreshCw className={`h-4 w-4 ${isRefreshing ? "animate-spin" : ""}`} />
        </Button>
      </div>

      {/* Recommendation Cards */}
      <div className="space-y-3">
        {recommendations.map((rec) => (
          <RecommendationCard
            key={rec.userId}
            recommendation={rec}
            isExpanded={expandedId === rec.userId}
            onToggleExpand={() =>
              setExpandedId(expandedId === rec.userId ? null : rec.userId)
            }
            onPing={onPing}
            onStartChat={onStartChat}
          />
        ))}
      </div>
    </div>
  );
};

interface RecommendationCardProps {
  recommendation: Recommendation;
  isExpanded: boolean;
  onToggleExpand: () => void;
  onPing: (userId: string, message?: string) => void;
  onStartChat: (userId: string, userName: string) => void;
}

const RecommendationCard = ({
  recommendation: rec,
  isExpanded,
  onToggleExpand,
  onPing,
  onStartChat,
}: RecommendationCardProps) => {
  const { user, matchScore, reasons, conversationStarters } = rec;

  return (
    <Card className="overflow-hidden">
      <CardContent className="p-4">
        {/* Main Info */}
        <div className="flex items-start gap-3">
          <Avatar className="h-12 w-12">
            <AvatarImage src={user.avatarUrl} />
            <AvatarFallback>
              {user.name.split(" ").map(n => n[0]).join("")}
            </AvatarFallback>
          </Avatar>

          <div className="flex-1 min-w-0">
            <div className="flex items-center justify-between">
              <h4 className="font-semibold truncate">{user.name}</h4>
              <Badge variant="secondary" className="ml-2 shrink-0">
                {matchScore}% match
              </Badge>
            </div>
            <p className="text-sm text-muted-foreground truncate">
              {user.role} at {user.company}
            </p>

            {/* Social Links */}
            <div className="flex items-center gap-2 mt-1">
              {user.linkedInUrl && (
                <a href={user.linkedInUrl} target="_blank" rel="noopener">
                  <Linkedin className="h-4 w-4 text-muted-foreground hover:text-blue-600" />
                </a>
              )}
              {user.githubUsername && (
                <a href={`https://github.com/${user.githubUsername}`} target="_blank" rel="noopener">
                  <Github className="h-4 w-4 text-muted-foreground hover:text-foreground" />
                </a>
              )}
              {user.twitterHandle && (
                <a href={`https://twitter.com/${user.twitterHandle.replace("@", "")}`} target="_blank" rel="noopener">
                  <Twitter className="h-4 w-4 text-muted-foreground hover:text-blue-400" />
                </a>
              )}
            </div>
          </div>
        </div>

        {/* Why Connect - First Reason Always Visible */}
        <div className="mt-3 p-2 bg-muted/50 rounded-md">
          <p className="text-sm">
            <span className="font-medium text-amber-600">Why connect:</span>{" "}
            {reasons[0]}
          </p>
        </div>

        {/* Expandable Section */}
        {isExpanded && (
          <div className="mt-3 space-y-3 animate-in slide-in-from-top-2">
            {/* Additional Reasons */}
            {reasons.slice(1).map((reason, i) => (
              <p key={i} className="text-sm text-muted-foreground pl-2 border-l-2">
                {reason}
              </p>
            ))}

            {/* Conversation Starters */}
            <div className="space-y-2">
              <p className="text-xs font-medium text-muted-foreground uppercase">
                Conversation Starters
              </p>
              {conversationStarters.map((starter, i) => (
                <div
                  key={i}
                  className="p-2 bg-background border rounded-md text-sm cursor-pointer hover:border-primary"
                  onClick={() => onPing(rec.userId, starter)}
                >
                  "{starter}"
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Actions */}
        <div className="flex items-center justify-between mt-3 pt-3 border-t">
          <Button
            variant="ghost"
            size="sm"
            onClick={onToggleExpand}
          >
            {isExpanded ? (
              <>
                <ChevronUp className="h-4 w-4 mr-1" />
                Less
              </>
            ) : (
              <>
                <ChevronDown className="h-4 w-4 mr-1" />
                Why connect
              </>
            )}
          </Button>

          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => onPing(rec.userId)}
            >
              Ping
            </Button>
            <Button
              size="sm"
              onClick={() => onStartChat(rec.userId, user.name)}
            >
              <MessageCircle className="h-4 w-4 mr-1" />
              Chat
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};
```

### 4.2 Integrated Networking Sheet

Update the proximity widget to include both tabs:

```tsx
// In floating-proximity-widget.tsx, add tabs:

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { RecommendationsPanel } from "./recommendations-panel";

// Inside SheetContent:
<Tabs defaultValue="nearby" className="flex-1 flex flex-col">
  <TabsList className="mx-4 mt-2">
    <TabsTrigger value="nearby" className="flex-1">
      <MapPin className="h-4 w-4 mr-1" />
      Nearby
      {nearbyCount > 0 && (
        <Badge variant="secondary" className="ml-1">{nearbyCount}</Badge>
      )}
    </TabsTrigger>
    <TabsTrigger value="recommended" className="flex-1">
      <Sparkles className="h-4 w-4 mr-1" />
      For You
    </TabsTrigger>
  </TabsList>

  <TabsContent value="nearby" className="flex-1 overflow-hidden mt-0">
    <NearbyUsersPanel ... />
  </TabsContent>

  <TabsContent value="recommended" className="flex-1 overflow-auto mt-0 p-4">
    <RecommendationsPanel
      eventId={eventId}
      onPing={onSendPing}
      onStartChat={onStartChat}
    />
  </TabsContent>
</Tabs>
```

### 4.3 Hook for Recommendations

Create `globalconnect/src/hooks/use-recommendations.ts`:

```typescript
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuthStore } from "@/store/auth.store";

interface Recommendation {
  userId: string;
  matchScore: number;
  reasons: string[];
  conversationStarters: string[];
  user: {
    id: string;
    name: string;
    role: string;
    company: string;
    avatarUrl?: string;
    linkedInUrl?: string;
    githubUsername?: string;
    twitterHandle?: string;
  };
}

export function useRecommendations(eventId: string) {
  const { user } = useAuthStore();
  const queryClient = useQueryClient();

  const query = useQuery({
    queryKey: ["recommendations", eventId, user?.id],
    queryFn: async () => {
      const response = await fetch(
        `/api/oracle/recommendations/${eventId}/for/${user?.id}`
      );
      if (!response.ok) throw new Error("Failed to fetch recommendations");
      const data = await response.json();
      return data.recommendations as Recommendation[];
    },
    enabled: !!user?.id && !!eventId,
    staleTime: 1000 * 60 * 5, // 5 minutes
  });

  const refreshMutation = useMutation({
    mutationFn: async () => {
      const response = await fetch(
        `/api/oracle/recommendations/${eventId}/for/${user?.id}?refresh=true`
      );
      if (!response.ok) throw new Error("Failed to refresh");
      return response.json();
    },
    onSuccess: (data) => {
      queryClient.setQueryData(
        ["recommendations", eventId, user?.id],
        data.recommendations
      );
    },
  });

  return {
    recommendations: query.data ?? [],
    isLoading: query.isLoading,
    error: query.error,
    refresh: refreshMutation.mutate,
    isRefreshing: refreshMutation.isPending,
  };
}
```

---

## Phase 5: Triggers & Automation

### 5.1 When to Trigger Enrichment

```typescript
// Trigger enrichment when:
// 1. User completes registration with opt-in
// 2. User manually requests enrichment later
// 3. User updates profile significantly

// api-gateway/src/users/users.service.ts
async onRegistrationComplete(userId: string, optedInForEnrichment: boolean) {
  if (optedInForEnrichment) {
    await this.oracleClient.post(`/enrichment/enrich/${userId}`);
  }
}
```

### 5.2 When to Generate Recommendations

```typescript
// Trigger recommendation generation when:
// 1. User checks into an event
// 2. Daily cron job for active events
// 3. User manually refreshes

// Event check-in handler
async onEventCheckIn(userId: string, eventId: string) {
  // Generate recommendations in background
  await this.oracleClient.post(
    `/recommendations/${eventId}/for/${userId}`
  );
}

// Daily cron job (runs at 6 AM)
@Cron('0 6 * * *')
async refreshDailyRecommendations() {
  const activeEvents = await this.getActiveEvents();

  for (const event of activeEvents) {
    await this.oracleClient.post(
      `/recommendations/${event.id}/generate-all`
    );
  }
}
```

---

## Phase 6: Facilitated Huddles (Micro-Meetups)

> **The Key Insight:** 1:1 recommendations require someone to "reach out." Facilitated huddles let people "show up." This is fundamentally lower friction.

### 6.1 The Concept

Instead of: *"You should meet John Doe"*
Facilitate: *"4 people near you are also struggling with scaling DevOps - meet at the Coffee Station in 10 minutes?"*

**Why this works:**
- No one is "reaching out" - everyone is "showing up"
- Shared problem = instant conversation topic
- Time-boxed = low commitment
- Physical location = real interaction, not just chat

### 6.2 Database Schema

Add to schema:

```prisma
model Huddle {
  id              String   @id @default(cuid())
  eventId         String

  // What brings them together
  topic           String   // "Scaling DevOps Teams"
  problemStatement String? // "Struggling with CI/CD pipelines"
  sessionId       String?  // If spawned from a session

  // Where and when
  locationName    String   // "Coffee Station near Hall B"
  locationCoords  Json?    // { lat, lng } for indoor positioning
  scheduledAt     DateTime
  duration        Int      @default(15) // minutes

  // Status
  status          HuddleStatus @default(FORMING)
  minParticipants Int      @default(3)
  maxParticipants Int      @default(8)

  // Relations
  participants    HuddleParticipant[]
  event           Event    @relation(fields: [eventId], references: [id])

  createdAt       DateTime @default(now())

  @@index([eventId, status])
  @@index([scheduledAt])
}

model HuddleParticipant {
  id          String   @id @default(cuid())
  huddleId    String
  userId      String

  status      ParticipantStatus @default(INVITED)
  respondedAt DateTime?
  attendedAt  DateTime?

  huddle      Huddle   @relation(fields: [huddleId], references: [id])

  @@unique([huddleId, userId])
}

enum HuddleStatus {
  FORMING     // Looking for participants
  CONFIRMED   // Enough participants, happening soon
  IN_PROGRESS // Currently happening
  COMPLETED   // Finished
  CANCELLED   // Not enough participants
}

enum ParticipantStatus {
  INVITED     // Sent invite
  ACCEPTED    // Will attend
  DECLINED    // Won't attend
  ATTENDED    // Actually showed up
  NO_SHOW     // Accepted but didn't show
}
```

### 6.3 Huddle Generation Logic

```python
# oracle-ai-service/app/features/huddles/generator.py

class HuddleGenerator:
    """
    Generates huddle suggestions based on:
    1. Shared problems/challenges (from registration)
    2. Session attendance (people in same session)
    3. Proximity clusters (people already near each other)
    """

    async def generate_problem_based_huddles(
        self,
        event_id: str,
    ) -> List[HuddleSuggestion]:
        """Find clusters of people with similar problems."""

        # Get all attendees with their problems/challenges
        attendees = await self.get_attendees_with_problems(event_id)

        # Group by problem similarity using embeddings
        problem_clusters = await self.cluster_by_problem_similarity(
            attendees,
            min_cluster_size=3,
            max_cluster_size=8,
            similarity_threshold=0.75
        )

        suggestions = []
        for cluster in problem_clusters:
            # Generate a topic that captures the shared problem
            topic = await self.llm.generate(f"""
                These {len(cluster)} people have the following challenges:
                {[a.problem for a in cluster]}

                Generate a concise huddle topic (max 8 words) that captures
                what they have in common. Focus on the PROBLEM, not the solution.

                Examples:
                - "Scaling engineering teams past 50 people"
                - "Migrating legacy systems to cloud"
                - "Finding product-market fit in B2B"
            """)

            suggestions.append(HuddleSuggestion(
                topic=topic,
                participants=[a.user_id for a in cluster],
                reason="shared_problem",
            ))

        return suggestions

    async def generate_session_based_huddles(
        self,
        event_id: str,
        session_id: str,
    ) -> List[HuddleSuggestion]:
        """
        After a session ends, suggest huddles for deeper discussion.
        "Want to continue discussing [session topic] with 5 others?"
        """

        session = await self.get_session(session_id)
        attendees = await self.get_session_attendees(session_id)

        if len(attendees) < 6:
            return []  # Not enough for meaningful subgroups

        # Cluster by interests/questions they might have
        clusters = await self.cluster_session_attendees(
            attendees,
            session_topics=session.topics,
            target_size=5
        )

        suggestions = []
        for cluster in clusters:
            suggestions.append(HuddleSuggestion(
                topic=f"Deep dive: {session.title}",
                sessionId=session_id,
                participants=[a.user_id for a in cluster],
                reason="session_followup",
                suggestedLocation=self.find_nearby_meetup_spot(session.room),
            ))

        return suggestions

    async def generate_proximity_huddles(
        self,
        event_id: str,
    ) -> List[HuddleSuggestion]:
        """
        When multiple people with shared interests are physically close,
        suggest an impromptu huddle.
        """

        # Get current proximity clusters from Redis GEO
        clusters = await self.proximity_service.get_current_clusters(
            event_id,
            min_size=3,
            radius_meters=20
        )

        suggestions = []
        for cluster in clusters:
            # Check if they have meaningful overlap
            users = await self.get_users_with_profiles(cluster.user_ids)
            shared_interests = self.find_shared_interests(users)

            if not shared_interests:
                continue

            suggestions.append(HuddleSuggestion(
                topic=f"Quick chat: {shared_interests[0]}",
                participants=cluster.user_ids,
                reason="proximity_match",
                suggestedLocation=cluster.center_location,
                isImpromptu=True,
            ))

        return suggestions
```

### 6.4 Huddle Invitation Flow

```typescript
// real-time-service/src/huddles/huddles.gateway.ts

@WebSocketGateway({ namespace: '/huddles' })
export class HuddlesGateway {

  @SubscribeMessage('invite_to_huddle')
  async handleHuddleInvite(
    @ConnectedSocket() client: Socket,
    @MessageBody() data: { huddleId: string; userIds: string[] }
  ) {
    const huddle = await this.huddleService.getHuddle(data.huddleId);

    for (const userId of data.userIds) {
      // Send real-time invitation
      this.server.to(`user:${userId}`).emit('huddle_invitation', {
        huddleId: huddle.id,
        topic: huddle.topic,
        problemStatement: huddle.problemStatement,
        location: huddle.locationName,
        scheduledAt: huddle.scheduledAt,
        duration: huddle.duration,
        currentParticipants: huddle.participants.filter(p => p.status === 'ACCEPTED').length,
        maxParticipants: huddle.maxParticipants,
        // Key: show WHO else is going (if they accepted)
        confirmedAttendees: huddle.participants
          .filter(p => p.status === 'ACCEPTED')
          .map(p => ({ name: p.user.name, role: p.user.role, company: p.user.company })),
      });
    }
  }

  @SubscribeMessage('respond_to_huddle')
  async handleHuddleResponse(
    @ConnectedSocket() client: Socket,
    @MessageBody() data: { huddleId: string; response: 'accept' | 'decline' }
  ) {
    const userId = client.data.userId;

    await this.huddleService.recordResponse(data.huddleId, userId, data.response);

    // Notify other participants of new joiner
    if (data.response === 'accept') {
      const huddle = await this.huddleService.getHuddle(data.huddleId);
      const user = await this.userService.getUser(userId);

      // Broadcast to all participants
      for (const participant of huddle.participants) {
        if (participant.userId !== userId && participant.status === 'ACCEPTED') {
          this.server.to(`user:${participant.userId}`).emit('huddle_participant_joined', {
            huddleId: data.huddleId,
            newParticipant: {
              name: user.name,
              role: user.role,
              company: user.company,
            },
            totalConfirmed: huddle.participants.filter(p => p.status === 'ACCEPTED').length,
          });
        }
      }

      // Check if huddle is now confirmed (min participants reached)
      await this.huddleService.checkAndConfirmHuddle(data.huddleId);
    }
  }
}
```

### 6.4.1 Race Condition Handling for Huddle Responses

When multiple users accept a huddle invitation simultaneously, race conditions can occur (e.g., exceeding `maxParticipants`). Use optimistic locking to prevent overselling spots.

**Optimistic Locking Implementation:**

```typescript
// real-time-service/src/huddles/huddles.service.ts

import { PrismaClient, Prisma } from '@prisma/client';

@Injectable()
export class HuddlesService {
  constructor(private prisma: PrismaClient) {}

  /**
   * Record huddle response with optimistic locking.
   * Prevents race conditions when multiple users accept simultaneously.
   */
  async recordResponse(
    huddleId: string,
    userId: string,
    response: 'accept' | 'decline'
  ): Promise<{ success: boolean; error?: string }> {
    if (response === 'decline') {
      // Declines don't need locking
      await this.prisma.huddleParticipant.update({
        where: { huddleId_userId: { huddleId, userId } },
        data: { status: 'DECLINED', respondedAt: new Date() },
      });
      return { success: true };
    }

    // For accepts, use optimistic locking to prevent race conditions
    const MAX_RETRIES = 3;
    let retries = 0;

    while (retries < MAX_RETRIES) {
      try {
        return await this.prisma.$transaction(async (tx) => {
          // Step 1: Get current huddle state with lock
          const huddle = await tx.huddle.findUnique({
            where: { id: huddleId },
            include: {
              participants: {
                where: { status: 'ACCEPTED' },
              },
            },
          });

          if (!huddle) {
            return { success: false, error: 'Huddle not found' };
          }

          // Step 2: Check if there's still room
          const currentCount = huddle.participants.length;
          if (currentCount >= huddle.maxParticipants) {
            return {
              success: false,
              error: 'HUDDLE_FULL',
              message: 'This huddle is now full. Try another huddle or create your own!',
            };
          }

          // Step 3: Check version hasn't changed (optimistic lock)
          // Update participant AND increment version atomically
          await tx.huddle.update({
            where: {
              id: huddleId,
              version: huddle.version, // Optimistic lock check
            },
            data: {
              version: { increment: 1 },
            },
          });

          // Step 4: Record the acceptance
          await tx.huddleParticipant.update({
            where: { huddleId_userId: { huddleId, userId } },
            data: { status: 'ACCEPTED', respondedAt: new Date() },
          });

          return { success: true };
        }, {
          isolationLevel: Prisma.TransactionIsolationLevel.Serializable,
        });

      } catch (error) {
        if (error.code === 'P2025') {
          // Record not found - version mismatch, retry
          retries++;
          if (retries >= MAX_RETRIES) {
            return {
              success: false,
              error: 'CONCURRENT_UPDATE',
              message: 'Too many people accepting at once. Please try again.',
            };
          }
          // Brief delay before retry
          await new Promise(resolve => setTimeout(resolve, 100 * retries));
        } else {
          throw error;
        }
      }
    }

    return { success: false, error: 'MAX_RETRIES_EXCEEDED' };
  }

  /**
   * Check and confirm huddle when minimum participants reached.
   * Also handles the race-safe version.
   */
  async checkAndConfirmHuddle(huddleId: string): Promise<void> {
    await this.prisma.$transaction(async (tx) => {
      const huddle = await tx.huddle.findUnique({
        where: { id: huddleId },
        include: {
          participants: { where: { status: 'ACCEPTED' } },
        },
      });

      if (!huddle || huddle.status === 'CONFIRMED') return;

      const acceptedCount = huddle.participants.length;
      const minRequired = huddle.minParticipants || 2;

      if (acceptedCount >= minRequired) {
        await tx.huddle.update({
          where: { id: huddleId },
          data: { status: 'CONFIRMED', confirmedAt: new Date() },
        });
      }
    });
  }
}
```

**Required Schema Addition:**

```prisma
// Add to Huddle model in prisma/schema.prisma

model Huddle {
  // ... existing fields ...

  // Optimistic locking version
  version Int @default(0)
}
```

**Frontend Handling for Full Huddles:**

```typescript
// Update gateway to emit appropriate error

@SubscribeMessage('respond_to_huddle')
async handleHuddleResponse(
  @ConnectedSocket() client: Socket,
  @MessageBody() data: { huddleId: string; response: 'accept' | 'decline' }
) {
  const userId = client.data.userId;
  const result = await this.huddleService.recordResponse(
    data.huddleId,
    userId,
    data.response
  );

  if (!result.success) {
    // Emit error back to the client
    client.emit('huddle_response_error', {
      huddleId: data.huddleId,
      error: result.error,
      message: result.message,
    });
    return;
  }

  // Success - proceed with normal flow
  // ... existing broadcast logic ...
}
```

### 6.5 Frontend: Huddle Invitation Card

```tsx
// globalconnect/src/components/features/huddles/huddle-invitation.tsx

interface HuddleInvitationProps {
  invitation: {
    huddleId: string;
    topic: string;
    problemStatement?: string;
    location: string;
    scheduledAt: Date;
    duration: number;
    currentParticipants: number;
    maxParticipants: number;
    confirmedAttendees: Array<{ name: string; role: string; company: string }>;
  };
  onAccept: () => void;
  onDecline: () => void;
}

export const HuddleInvitation = ({ invitation, onAccept, onDecline }: HuddleInvitationProps) => {
  const timeUntil = formatDistanceToNow(invitation.scheduledAt, { addSuffix: true });

  return (
    <Card className="border-amber-200 bg-amber-50/50">
      <CardContent className="p-4">
        {/* Header */}
        <div className="flex items-start gap-3">
          <div className="p-2 rounded-full bg-amber-100">
            <Users className="h-5 w-5 text-amber-600" />
          </div>
          <div className="flex-1">
            <h4 className="font-semibold text-amber-900">{invitation.topic}</h4>
            {invitation.problemStatement && (
              <p className="text-sm text-amber-700 mt-1">
                "{invitation.problemStatement}"
              </p>
            )}
          </div>
        </div>

        {/* Details */}
        <div className="mt-4 space-y-2 text-sm">
          <div className="flex items-center gap-2 text-muted-foreground">
            <MapPin className="h-4 w-4" />
            <span>{invitation.location}</span>
          </div>
          <div className="flex items-center gap-2 text-muted-foreground">
            <Clock className="h-4 w-4" />
            <span>{timeUntil} • {invitation.duration} minutes</span>
          </div>
        </div>

        {/* Who's going */}
        <div className="mt-4">
          <p className="text-xs text-muted-foreground mb-2">
            {invitation.currentParticipants} of {invitation.maxParticipants} spots filled
          </p>

          {invitation.confirmedAttendees.length > 0 && (
            <div className="space-y-1">
              <p className="text-xs font-medium">Already joining:</p>
              {invitation.confirmedAttendees.slice(0, 3).map((attendee, i) => (
                <p key={i} className="text-xs text-muted-foreground">
                  {attendee.name} • {attendee.role} at {attendee.company}
                </p>
              ))}
              {invitation.confirmedAttendees.length > 3 && (
                <p className="text-xs text-muted-foreground">
                  +{invitation.confirmedAttendees.length - 3} more
                </p>
              )}
            </div>
          )}
        </div>

        {/* Actions */}
        <div className="mt-4 flex gap-2">
          <Button
            variant="outline"
            size="sm"
            className="flex-1"
            onClick={onDecline}
          >
            Can't make it
          </Button>
          <Button
            size="sm"
            className="flex-1 bg-amber-600 hover:bg-amber-700"
            onClick={onAccept}
          >
            <Check className="h-4 w-4 mr-1" />
            I'll be there
          </Button>
        </div>
      </CardContent>
    </Card>
  );
};
```

### 6.6 Problem Statement During Registration

Add to registration flow - capture specific challenges:

```typescript
// In registration step 2 (interests-goals.tsx)

interface ProblemStatementStepProps {
  value: string;
  onChange: (value: string) => void;
}

export const ProblemStatementStep = ({ value, onChange }: ProblemStatementStepProps) => {
  const suggestions = [
    "Scaling my engineering team",
    "Finding product-market fit",
    "Raising our next funding round",
    "Migrating to cloud infrastructure",
    "Building a remote-first culture",
    "Improving developer productivity",
  ];

  return (
    <div className="space-y-4">
      <div>
        <h3 className="font-medium">What's your biggest challenge right now?</h3>
        <p className="text-sm text-muted-foreground">
          We'll connect you with others facing the same challenge
        </p>
      </div>

      <Textarea
        placeholder="e.g., We're struggling to hire senior engineers in a competitive market..."
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="min-h-[80px]"
      />

      <div className="space-y-2">
        <p className="text-xs text-muted-foreground">Or pick a common one:</p>
        <div className="flex flex-wrap gap-2">
          {suggestions.map((suggestion) => (
            <Badge
              key={suggestion}
              variant={value === suggestion ? "default" : "outline"}
              className="cursor-pointer"
              onClick={() => onChange(suggestion)}
            >
              {suggestion}
            </Badge>
          ))}
        </div>
      </div>
    </div>
  );
};
```

### 6.7 Huddle Triggers

```typescript
// When to suggest huddles:

// 1. After session ends (session-based)
@OnEvent('session.ended')
async onSessionEnded(sessionId: string) {
  const suggestions = await this.huddleGenerator.generateSessionBasedHuddles(
    eventId,
    sessionId
  );
  await this.createAndInvite(suggestions);
}

// 2. Periodic scan for problem clusters (every 30 min)
@Cron('*/30 * * * *')
async scanForProblemHuddles() {
  const activeEvents = await this.getActiveEvents();
  for (const event of activeEvents) {
    const suggestions = await this.huddleGenerator.generateProblemBasedHuddles(event.id);
    await this.createAndInvite(suggestions);
  }
}

// 3. Proximity-triggered (real-time)
@OnEvent('proximity.cluster_detected')
async onProximityCluster(cluster: ProximityCluster) {
  const suggestions = await this.huddleGenerator.generateProximityHuddles(cluster);
  await this.createAndInvite(suggestions);
}
```

### 6.8 Success Metrics for Huddles

| Metric | Target | Why It Matters |
|--------|--------|----------------|
| Invite → Accept Rate | >40% | Are huddles compelling? |
| Accept → Attend Rate | >70% | Do people follow through? |
| Avg Huddle Size | 4-6 | Sweet spot for conversation |
| Post-Huddle Connections | >1 per huddle | Did meaningful connections form? |
| Repeat Huddle Joins | >30% | Do people come back? |

---

## Phase 7: Post-Event Value & Retention

> **The Core Problem:** Current event apps are "throwaway" - downloaded before, deleted after. We need to make GlobalConnect valuable BETWEEN events, not just during them.

### 7.1 The Retention Challenge

**Why people delete event apps:**
- No value after event ends
- No reason to come back
- Connections made at event aren't maintained
- Next event = download a different app

**Our opportunity:**
- Turn event connections into a persistent professional network
- Cross-event value (your connections attend other events)
- Follow-up automation that drives real outcomes
- Become the "LinkedIn for event-based networking"

### 7.2 Database Schema for Persistent Connections

```prisma
model Connection {
  id              String   @id @default(cuid())

  // The two connected users
  userId          String
  connectedUserId String

  // Origin context
  originEventId   String   // Where they first connected
  originType      ConnectionOrigin // How they connected

  // Relationship strength
  strength        ConnectionStrength @default(WEAK)
  interactionCount Int      @default(1)
  lastInteractionAt DateTime @default(now())

  // Follow-up tracking
  followUpSent    Boolean  @default(false)
  followUpSentAt  DateTime?
  followUpResponse FollowUpResponse?

  // Notes (user can add context)
  notes           String?

  createdAt       DateTime @default(now())
  updatedAt       DateTime @updatedAt

  @@unique([userId, connectedUserId])
  @@index([userId, strength])
  @@index([userId, lastInteractionAt])
}

enum ConnectionOrigin {
  PING            // Connected via ping
  HUDDLE          // Met at a huddle
  DM              // Started conversation via DM
  RECOMMENDATION  // Connected from a recommendation
  MANUAL          // Manually added
}

enum ConnectionStrength {
  WEAK            // Single interaction
  MODERATE        // Multiple interactions OR follow-up exchanged
  STRONG          // Ongoing relationship (3+ events together OR active DMs)
}

enum FollowUpResponse {
  PENDING
  RESPONDED
  NO_RESPONSE
  MEETING_SCHEDULED
}

model ConnectionActivity {
  id            String   @id @default(cuid())
  connectionId  String
  activityType  ActivityType
  eventId       String?  // If activity happened at an event
  metadata      Json?    // Additional context

  createdAt     DateTime @default(now())

  connection    Connection @relation(fields: [connectionId], references: [id])

  @@index([connectionId, createdAt])
}

enum ActivityType {
  FIRST_CONTACT       // Initial ping/DM
  DM_EXCHANGED        // Sent messages
  HUDDLE_TOGETHER     // Attended same huddle
  SAME_EVENT          // Both at same event
  FOLLOW_UP_SENT      // Post-event follow-up
  FOLLOW_UP_RESPONSE  // They responded
  MEETING_SCHEDULED   // External meeting set
  RECONNECTED         // Met again at another event
}
```

### 7.2.1 Schema Unification Note

> **⚠️ IMPORTANT: Before implementing the Connection schema above, audit existing models in `real-time-service` for overlap.**

The existing codebase may already have connection-related models that should be unified rather than duplicated:

**Audit Checklist:**

```bash
# Search for existing connection/relationship models
grep -r "model.*Connection" real-time-service/prisma/
grep -r "model.*Relationship" real-time-service/prisma/
grep -r "model.*Contact" real-time-service/prisma/
grep -r "model.*Network" real-time-service/prisma/
```

**Potential Overlaps to Check:**

| Location | Model | May Overlap With |
|----------|-------|------------------|
| `real-time-service/prisma/schema.prisma` | `UserConnection` | `Connection` |
| `real-time-service/prisma/schema.prisma` | `PingHistory` | `ConnectionActivity` |
| `networking/connections/` | Connection service | Post-event connections |

**Resolution Strategy:**

1. **If existing `UserConnection` model exists:**
   - Extend it with `originEventId`, `strength`, and follow-up fields
   - Don't create a duplicate `Connection` model

2. **If `PingHistory` exists:**
   - Consider merging with `ConnectionActivity` or creating a view

3. **Migration Path:**
   ```prisma
   // Example: Extending existing model instead of duplicating
   model UserConnection {
     // ... existing fields ...

     // ADD these fields for matchmaking feature
     originEventId     String?
     originType        ConnectionOrigin?
     strength          ConnectionStrength @default(WEAK)
     followUpSent      Boolean @default(false)
     followUpSentAt    DateTime?
   }
   ```

**Decision Required Before Implementation:**
- [ ] Audit complete - no overlapping models found → Use schema as-is
- [ ] Overlapping models found → Create migration to extend existing models
- [ ] Document which service owns the `Connection` model (recommend: `real-time-service`)

### 7.3 Post-Event Follow-Up System

**Automated follow-up reminders (24-72 hours after event):**

```typescript
// oracle-ai-service/app/features/followup/generator.py

class FollowUpGenerator:
    """
    Generates personalized follow-up suggestions after an event ends.
    """

    async def generate_follow_ups(
        self,
        user_id: str,
        event_id: str
    ) -> List[FollowUpSuggestion]:
        """Generate follow-up suggestions for connections made at event."""

        # Get all connections made at this event
        connections = await self.get_event_connections(user_id, event_id)

        if not connections:
            return []

        suggestions = []
        for conn in connections:
            # Get context about the connection
            context = await self.get_connection_context(conn)

            # Generate personalized follow-up message
            message = await self.llm.generate(f"""
                Generate a brief, professional follow-up message.

                Context:
                - You met {conn.connected_user.name} at {context.event_name}
                - They are: {conn.connected_user.role} at {conn.connected_user.company}
                - How you connected: {context.origin_description}
                - Shared interests: {context.shared_interests}
                - Their challenge: {conn.connected_user.problem_statement or 'Not specified'}

                Generate a 2-3 sentence follow-up that:
                1. References how you met (specific, not generic)
                2. Mentions something you discussed or have in common
                3. Suggests a concrete next step (coffee chat, intro, resource share)

                Keep it warm but professional. No emojis.
            """)

            suggestions.append(FollowUpSuggestion(
                connectionId=conn.id,
                connectedUser=conn.connected_user,
                suggestedMessage=message,
                reason=context.origin_description,
                priority=self.calculate_priority(conn, context),
            ))

        # Sort by priority (strongest connections first)
        return sorted(suggestions, key=lambda x: x.priority, reverse=True)

    def calculate_priority(self, conn, context) -> int:
        """Higher priority = more likely to be valuable follow-up."""
        score = 0

        # Multiple interactions = higher priority
        score += conn.interaction_count * 10

        # Huddle connections are stronger
        if conn.origin_type == 'HUDDLE':
            score += 20

        # Shared problems = higher priority
        if context.shared_problem:
            score += 30

        # They're hiring and you're looking (or vice versa)
        if context.goal_alignment:
            score += 40

        return score
```

### 7.4 Follow-Up Notification UI

```tsx
// globalconnect/src/components/features/followup/follow-up-reminder.tsx

interface FollowUpReminderProps {
  suggestions: FollowUpSuggestion[];
  onSendFollowUp: (connectionId: string, message: string) => void;
  onDismiss: (connectionId: string) => void;
  onSnooze: (connectionId: string, days: number) => void;
}

export const FollowUpReminder = ({
  suggestions,
  onSendFollowUp,
  onDismiss,
  onSnooze,
}: FollowUpReminderProps) => {
  const [editingMessage, setEditingMessage] = useState<Record<string, string>>({});

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center gap-2">
        <Bell className="h-5 w-5 text-blue-600" />
        <h3 className="font-semibold">Follow Up With Your New Connections</h3>
      </div>

      <p className="text-sm text-muted-foreground">
        You met {suggestions.length} people at the event. A quick follow-up can turn
        a conversation into a lasting connection.
      </p>

      {/* Suggestions */}
      <div className="space-y-3">
        {suggestions.map((suggestion) => (
          <Card key={suggestion.connectionId} className="overflow-hidden">
            <CardContent className="p-4">
              {/* Person info */}
              <div className="flex items-start gap-3">
                <Avatar className="h-10 w-10">
                  <AvatarImage src={suggestion.connectedUser.avatarUrl} />
                  <AvatarFallback>
                    {suggestion.connectedUser.name.split(" ").map(n => n[0]).join("")}
                  </AvatarFallback>
                </Avatar>
                <div className="flex-1">
                  <h4 className="font-medium">{suggestion.connectedUser.name}</h4>
                  <p className="text-sm text-muted-foreground">
                    {suggestion.connectedUser.role} at {suggestion.connectedUser.company}
                  </p>
                  <p className="text-xs text-muted-foreground mt-1">
                    {suggestion.reason}
                  </p>
                </div>
              </div>

              {/* Suggested message */}
              <div className="mt-3">
                <Textarea
                  value={editingMessage[suggestion.connectionId] ?? suggestion.suggestedMessage}
                  onChange={(e) => setEditingMessage({
                    ...editingMessage,
                    [suggestion.connectionId]: e.target.value
                  })}
                  className="text-sm min-h-[80px]"
                />
              </div>

              {/* Actions */}
              <div className="mt-3 flex items-center justify-between">
                <div className="flex gap-2">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => onDismiss(suggestion.connectionId)}
                  >
                    Skip
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => onSnooze(suggestion.connectionId, 3)}
                  >
                    Remind me later
                  </Button>
                </div>
                <Button
                  size="sm"
                  onClick={() => onSendFollowUp(
                    suggestion.connectionId,
                    editingMessage[suggestion.connectionId] ?? suggestion.suggestedMessage
                  )}
                >
                  <Send className="h-4 w-4 mr-1" />
                  Send Follow-Up
                </Button>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
};
```

### 7.5 Cross-Event Network Effects

**"Your connections are attending" - drive event discovery:**

```typescript
// api-gateway/src/events/events.service.ts

async getEventsWithConnections(userId: string): Promise<EventWithConnections[]> {
  // Get user's connections
  const connections = await this.connectionService.getUserConnections(userId);
  const connectionUserIds = connections.map(c => c.connectedUserId);

  // Get upcoming events
  const upcomingEvents = await this.eventService.getUpcomingEvents();

  // For each event, find which connections are attending
  const eventsWithConnections = await Promise.all(
    upcomingEvents.map(async (event) => {
      const attendees = await this.eventService.getEventAttendees(event.id);
      const connectionsAttending = attendees.filter(
        a => connectionUserIds.includes(a.userId)
      );

      return {
        ...event,
        connectionsAttending: connectionsAttending.length,
        connectionDetails: connectionsAttending.slice(0, 3).map(a => ({
          name: a.name,
          avatarUrl: a.avatarUrl,
        })),
      };
    })
  );

  // Sort by connections attending (more connections = higher priority)
  return eventsWithConnections
    .filter(e => e.connectionsAttending > 0)
    .sort((a, b) => b.connectionsAttending - a.connectionsAttending);
}
```

**UI for event discovery:**

```tsx
// globalconnect/src/components/features/events/events-with-network.tsx

export const EventsWithNetwork = ({ events }: { events: EventWithConnections[] }) => {
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <Users className="h-5 w-5 text-primary" />
        <h3 className="font-semibold">Events Your Network is Attending</h3>
      </div>

      {events.map((event) => (
        <Card key={event.id} className="overflow-hidden">
          <CardContent className="p-4">
            <div className="flex items-start justify-between">
              <div>
                <h4 className="font-medium">{event.name}</h4>
                <p className="text-sm text-muted-foreground">
                  {format(event.startDate, 'MMM d, yyyy')} • {event.location}
                </p>
              </div>

              {/* Connections attending */}
              <div className="flex items-center gap-2">
                <div className="flex -space-x-2">
                  {event.connectionDetails.map((conn, i) => (
                    <Avatar key={i} className="h-8 w-8 border-2 border-background">
                      <AvatarImage src={conn.avatarUrl} />
                      <AvatarFallback>{conn.name[0]}</AvatarFallback>
                    </Avatar>
                  ))}
                </div>
                <span className="text-sm font-medium text-primary">
                  {event.connectionsAttending} connection{event.connectionsAttending > 1 ? 's' : ''}
                </span>
              </div>
            </div>

            <Button className="w-full mt-3" variant="outline">
              View Event
            </Button>
          </CardContent>
        </Card>
      ))}
    </div>
  );
};
```

### 7.6 "Your Professional Event Network" - Persistent Value

**The core retention feature: a network you build across events.**

```tsx
// globalconnect/src/app/(main)/network/page.tsx

export default function NetworkPage() {
  const { connections, isLoading } = useConnections();
  const { stats } = useNetworkStats();

  return (
    <div className="container max-w-4xl py-8">
      {/* Network Stats */}
      <div className="grid grid-cols-3 gap-4 mb-8">
        <Card>
          <CardContent className="p-4 text-center">
            <p className="text-3xl font-bold">{stats.totalConnections}</p>
            <p className="text-sm text-muted-foreground">Connections</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 text-center">
            <p className="text-3xl font-bold">{stats.eventsAttended}</p>
            <p className="text-sm text-muted-foreground">Events</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 text-center">
            <p className="text-3xl font-bold">{stats.followUpRate}%</p>
            <p className="text-sm text-muted-foreground">Follow-up Rate</p>
          </CardContent>
        </Card>
      </div>

      {/* Filter tabs */}
      <Tabs defaultValue="all">
        <TabsList>
          <TabsTrigger value="all">All Connections</TabsTrigger>
          <TabsTrigger value="strong">Strong</TabsTrigger>
          <TabsTrigger value="recent">Recent</TabsTrigger>
          <TabsTrigger value="need-followup">Need Follow-up</TabsTrigger>
        </TabsList>

        <TabsContent value="all" className="mt-4">
          <ConnectionsList connections={connections} />
        </TabsContent>

        <TabsContent value="strong">
          <ConnectionsList
            connections={connections.filter(c => c.strength === 'STRONG')}
          />
        </TabsContent>

        <TabsContent value="recent">
          <ConnectionsList
            connections={connections.sort(
              (a, b) => new Date(b.lastInteractionAt).getTime() - new Date(a.lastInteractionAt).getTime()
            ).slice(0, 20)}
          />
        </TabsContent>

        <TabsContent value="need-followup">
          <ConnectionsList
            connections={connections.filter(
              c => !c.followUpSent && daysSince(c.createdAt) > 2 && daysSince(c.createdAt) < 14
            )}
            showFollowUpPrompt
          />
        </TabsContent>
      </Tabs>
    </div>
  );
}
```

### 7.7 Connection Activity Feed

**"Remember that conversation with James? He just posted about..."**

```typescript
// Keep users engaged with connection updates

interface ConnectionUpdate {
  connectionId: string;
  connectedUser: User;
  updateType: 'attending_event' | 'role_change' | 'company_change' | 'shared_event';
  description: string;
  actionable: boolean;
  suggestedAction?: string;
}

async function getConnectionUpdates(userId: string): Promise<ConnectionUpdate[]> {
  const connections = await getConnections(userId);
  const updates: ConnectionUpdate[] = [];

  for (const conn of connections) {
    // Check if they're attending an upcoming event
    const theirEvents = await getUpcomingEventsForUser(conn.connectedUserId);
    const myEvents = await getUpcomingEventsForUser(userId);

    const sharedUpcoming = theirEvents.filter(
      e => myEvents.some(me => me.id === e.id)
    );

    if (sharedUpcoming.length > 0) {
      updates.push({
        connectionId: conn.id,
        connectedUser: conn.connectedUser,
        updateType: 'shared_event',
        description: `You'll both be at ${sharedUpcoming[0].name}`,
        actionable: true,
        suggestedAction: 'Schedule a meetup',
      });
    }

    // Check for role/company changes (from re-enrichment)
    if (conn.connectedUser.roleChangedAt &&
        daysSince(conn.connectedUser.roleChangedAt) < 30) {
      updates.push({
        connectionId: conn.id,
        connectedUser: conn.connectedUser,
        updateType: 'role_change',
        description: `Now ${conn.connectedUser.role} at ${conn.connectedUser.company}`,
        actionable: true,
        suggestedAction: 'Congratulate them',
      });
    }
  }

  return updates;
}
```

### 7.8 Cold Start Strategy

**How to provide value at the FIRST event (no prior network):**

1. **Profile enrichment still works** - Even without connections, we enrich their profile and provide recommendations based on goals/interests

2. **Problem-based matching** - "5 other first-timers are also working on [your problem]" - doesn't require prior connections

3. **Session-based huddles** - Attending the same session creates instant connection opportunity

4. **Recommendation quality** - LLM recommendations are based on profile match, not network - works from event #1

5. **Immediate value proposition:**
   - "Here are 10 people you should meet at this event and WHY"
   - Not "here's your network" (empty) but "here's who you could build a network WITH"

```typescript
// First-event experience
async function getFirstEventRecommendations(userId: string, eventId: string) {
  // Even for first-time users, we can provide value

  return {
    // Profile-based recommendations (works without network)
    recommendations: await generateRecommendations(userId, eventId),

    // Problem-cluster suggestions
    problemPeers: await findPeopleWithSimilarProblems(userId, eventId),

    // Session-based suggestions
    sessionSuggestions: await getSuggestedSessionsWithPeers(userId, eventId),

    // Explicit messaging for first-timers
    welcomeMessage: "This is your first GlobalConnect event! Here's how to make the most of it...",
  };
}
```

### 7.9 Retention Triggers

```typescript
// Automated engagement to keep users coming back

// 1. Post-event follow-up (24-72 hours after)
@Cron('0 10 * * *') // 10 AM daily
async sendFollowUpReminders() {
  const recentEvents = await this.getEventsEndedWithin(72); // hours

  for (const event of recentEvents) {
    const attendees = await this.getAttendeesWhoMadeConnections(event.id);

    for (const attendee of attendees) {
      await this.notificationService.send(attendee.userId, {
        type: 'follow_up_reminder',
        title: 'Follow up with your new connections',
        body: `You met ${attendee.connectionCount} people at ${event.name}. A quick message can turn a conversation into an opportunity.`,
      });
    }
  }
}

// 2. Connection attending event notification
@OnEvent('event.registration')
async notifyConnectionsAttending(eventId: string, userId: string) {
  const connections = await this.getConnections(userId);

  for (const conn of connections) {
    const isAttending = await this.isUserAttendingEvent(conn.connectedUserId, eventId);

    if (isAttending) {
      await this.notificationService.send(userId, {
        type: 'connection_attending',
        title: `${conn.connectedUser.name} is also attending`,
        body: `Your connection from ${conn.originEvent.name} is going to this event too.`,
      });
    }
  }
}

// 3. Reconnection opportunity
@OnEvent('event.checkin')
async checkForReconnections(eventId: string, userId: string) {
  // Find connections also at this event
  const connectionsAtEvent = await this.getConnectionsAtEvent(userId, eventId);

  if (connectionsAtEvent.length > 0) {
    await this.notificationService.send(userId, {
      type: 'reconnection_opportunity',
      title: `${connectionsAtEvent.length} of your connections are here!`,
      body: 'Tap to see who and where they are.',
      data: { connectionIds: connectionsAtEvent.map(c => c.id) },
    });
  }
}

// 4. Monthly network digest
@Cron('0 9 1 * *') // 1st of each month at 9 AM
async sendMonthlyDigest() {
  const users = await this.getActiveUsers();

  for (const user of users) {
    const stats = await this.getMonthlyNetworkStats(user.id);

    if (stats.newConnections > 0 || stats.upcomingEventsWithConnections > 0) {
      await this.emailService.send(user.email, {
        template: 'monthly_digest',
        data: {
          newConnections: stats.newConnections,
          totalConnections: stats.totalConnections,
          upcomingEvents: stats.upcomingEventsWithConnections,
          topConnection: stats.mostInteractedConnection,
        },
      });
    }
  }
}
```

### 7.10 Success Metrics (Redefined)

**Old metrics (what incumbents measure):**
- App downloads
- % who opened the app
- Sessions viewed

**New metrics (what actually matters):**

| Metric | Target | Why It Matters |
|--------|--------|----------------|
| **Connections per attendee** | >3 | Are people actually networking? |
| **Follow-up sent rate** | >40% | Do connections extend beyond the event? |
| **Follow-up response rate** | >30% | Are follow-ups leading to conversations? |
| **Cross-event reconnection** | >20% | Do people meet again at future events? |
| **App retention (30-day)** | >25% | Do they keep the app after the event? |
| **Event discovery via network** | >15% | Are they finding events through connections? |
| **Network growth rate** | +5/event | Is their network actually growing? |

### 7.11 The Retention Loop

```
┌─────────────────────────────────────────────────────────────────┐
│                    THE RETENTION FLYWHEEL                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│    ┌──────────┐         ┌──────────┐         ┌──────────┐       │
│    │  ATTEND  │────────▶│  CONNECT │────────▶│ FOLLOW UP│       │
│    │  EVENT   │         │ (Ping,   │         │ (24-72h  │       │
│    └──────────┘         │  Huddle) │         │  after)  │       │
│         ▲               └──────────┘         └────┬─────┘       │
│         │                                         │              │
│         │                                         ▼              │
│    ┌────┴─────┐                            ┌──────────┐         │
│    │ DISCOVER │◀───────────────────────────│  BUILD   │         │
│    │ (Network │                            │ NETWORK  │         │
│    │  attending)                           └──────────┘         │
│    └──────────┘                                  │               │
│         ▲                                        │               │
│         │            ┌──────────┐               │               │
│         └────────────│  STAY    │◀──────────────┘               │
│                      │ ENGAGED  │                                │
│                      │ (Updates,│                                │
│                      │  Digest) │                                │
│                      └──────────┘                                │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Key insight:** Each stage feeds the next. More connections → more follow-ups → stronger network → more events discovered → more connections. This is the flywheel that incumbents don't have.

---

## Phase 8: Operational Resilience

> **The Reality:** Enrichment will fail for many users. APIs have rate limits. Small events need different algorithms. This phase ensures the system degrades gracefully.

### 8.1 Enrichment Failure Strategy

**Why enrichment fails:**
- Non-English names (harder to find)
- Common names ("John Smith" + "Engineer" = ???)
- Private profiles or minimal online presence
- Startups/companies not well-indexed
- API rate limits hit

**Tiered Profile System:**

```prisma
enum ProfileTier {
  TIER_1_RICH      // Found 3+ sources - full enrichment
  TIER_2_BASIC     // Found 1-2 sources - partial enrichment
  TIER_3_MANUAL    // No sources found - manual input only
  TIER_0_PENDING   // Not yet attempted
}

// Add to UserProfile model
model UserProfile {
  // ... existing fields ...

  profileTier       ProfileTier @default(TIER_0_PENDING)
  enrichmentAttempts Int        @default(0)
  lastEnrichmentError String?
}
```

**Fallback Logic:**

```python
# oracle-ai-service/app/features/enrichment/fallback.py

class EnrichmentFallbackHandler:
    """
    Handles enrichment failures gracefully.
    Target: 60%+ success rate for enrichment.
    """

    async def handle_enrichment_result(
        self,
        user_id: str,
        result: EnrichmentResult
    ) -> ProfileTier:
        """Determine profile tier based on enrichment results."""

        sources_found = len(result.sources)

        if sources_found >= 3:
            tier = ProfileTier.TIER_1_RICH
            await self.mark_as_enriched(user_id, tier, result)

        elif sources_found >= 1:
            tier = ProfileTier.TIER_2_BASIC
            await self.mark_as_enriched(user_id, tier, result)
            # Prompt user to add missing info
            await self.send_completion_prompt(user_id, result.missing_sources)

        else:
            tier = ProfileTier.TIER_3_MANUAL
            await self.mark_enrichment_failed(user_id)
            # Prompt user to manually add profiles
            await self.send_manual_input_request(user_id)

        return tier

    async def send_completion_prompt(
        self,
        user_id: str,
        missing_sources: List[str]
    ):
        """Ask user to manually add missing profile links."""

        await self.notification_service.send(user_id, {
            "type": "profile_incomplete",
            "title": "Complete your profile for better matches",
            "body": f"We couldn't find your {', '.join(missing_sources)}. Add them manually for better recommendations.",
            "action": {
                "type": "open_profile_edit",
                "highlight_fields": missing_sources
            }
        })

    async def send_manual_input_request(self, user_id: str):
        """For TIER_3 users, prompt for manual input."""

        await self.notification_service.send(user_id, {
            "type": "profile_manual_needed",
            "title": "Help us find better matches for you",
            "body": "Add your LinkedIn or GitHub to get personalized recommendations.",
            "action": {
                "type": "open_profile_edit",
                "fields": ["linkedInUrl", "githubUsername", "bio", "skillsToOffer"]
            }
        })
```

**UI: Profile Completion Prompt**

```tsx
// globalconnect/src/components/features/profile/profile-completion-banner.tsx

interface ProfileCompletionBannerProps {
  tier: ProfileTier;
  missingFields: string[];
  onComplete: () => void;
}

export const ProfileCompletionBanner = ({
  tier,
  missingFields,
  onComplete,
}: ProfileCompletionBannerProps) => {
  if (tier === "TIER_1_RICH") return null;

  const getMessage = () => {
    switch (tier) {
      case "TIER_2_BASIC":
        return {
          icon: <AlertCircle className="h-5 w-5 text-amber-500" />,
          title: "Almost there!",
          description: "Add a few more details to get better match recommendations.",
          urgency: "medium",
        };
      case "TIER_3_MANUAL":
        return {
          icon: <UserPlus className="h-5 w-5 text-blue-500" />,
          title: "Complete your profile",
          description: "We couldn't find your public profiles. Add them manually to unlock AI-powered recommendations.",
          urgency: "high",
        };
      default:
        return null;
    }
  };

  const message = getMessage();
  if (!message) return null;

  return (
    <Card className={cn(
      "border-l-4",
      message.urgency === "high" ? "border-l-blue-500 bg-blue-50/50" : "border-l-amber-500 bg-amber-50/50"
    )}>
      <CardContent className="p-4">
        <div className="flex items-start gap-3">
          {message.icon}
          <div className="flex-1">
            <h4 className="font-medium">{message.title}</h4>
            <p className="text-sm text-muted-foreground mt-1">
              {message.description}
            </p>

            {missingFields.length > 0 && (
              <div className="flex flex-wrap gap-2 mt-3">
                {missingFields.map((field) => (
                  <Badge key={field} variant="outline">
                    {formatFieldName(field)}
                  </Badge>
                ))}
              </div>
            )}
          </div>

          <Button size="sm" onClick={onComplete}>
            Complete Profile
          </Button>
        </div>
      </CardContent>
    </Card>
  );
};
```

**Recommendation Handling for Different Tiers:**

```python
# Don't penalize TIER_3 users - they should still appear in recommendations

async def get_event_attendees_for_matching(event_id: str) -> List[AttendeeProfile]:
    """Get all attendees, regardless of enrichment tier."""

    attendees = await prisma.user.find_many(
        where={"eventRegistrations": {"some": {"eventId": event_id}}},
        include={"profile": True}
    )

    profiles = []
    for attendee in attendees:
        profile = build_matching_profile(attendee)

        # For TIER_3 users, rely on registration data
        if attendee.profile.profileTier == "TIER_3_MANUAL":
            profile["dataSource"] = "registration"
            profile["dataQuality"] = "basic"
        else:
            profile["dataSource"] = "enriched"
            profile["dataQuality"] = "rich"

        profiles.append(profile)

    return profiles
```

### 8.2 Rate Limiting & Throttling

**Tavily Rate Limiting:**

```python
# oracle-ai-service/app/core/rate_limiter.py

from asyncio import Semaphore
from datetime import datetime, timedelta
import asyncio

class RateLimiter:
    """
    Token bucket rate limiter for API calls.
    Prevents cost spikes and API hammering.
    """

    def __init__(self, rate_limit: int, period_seconds: int):
        self.rate_limit = rate_limit
        self.period = period_seconds
        self.tokens = rate_limit
        self.last_refill = datetime.utcnow()
        self.lock = asyncio.Lock()

    async def acquire(self):
        """Wait until a token is available."""
        async with self.lock:
            await self._refill()

            while self.tokens <= 0:
                # Wait for next refill period
                wait_time = self.period / self.rate_limit
                await asyncio.sleep(wait_time)
                await self._refill()

            self.tokens -= 1

    async def _refill(self):
        """Refill tokens based on elapsed time."""
        now = datetime.utcnow()
        elapsed = (now - self.last_refill).total_seconds()

        tokens_to_add = int(elapsed * self.rate_limit / self.period)
        if tokens_to_add > 0:
            self.tokens = min(self.rate_limit, self.tokens + tokens_to_add)
            self.last_refill = now


# Global rate limiters
tavily_limiter = RateLimiter(rate_limit=100, period_seconds=3600)  # 100/hour
github_limiter = RateLimiter(rate_limit=50, period_seconds=3600)   # 50/hour (conservative)
llm_limiter = RateLimiter(rate_limit=500, period_seconds=3600)     # 500/hour


# Usage in enrichment agent
async def search_with_tavily(query: str) -> dict:
    await tavily_limiter.acquire()

    try:
        return await tavily_client.search(query)
    except RateLimitError:
        logger.warning(f"Tavily rate limit hit, backing off")
        await asyncio.sleep(60)  # Back off for 1 minute
        return await search_with_tavily(query)  # Retry


async def fetch_github_profile(username: str) -> Optional[dict]:
    await github_limiter.acquire()

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://api.github.com/users/{username}",
                headers={"Authorization": f"token {settings.GITHUB_TOKEN}"} if settings.GITHUB_TOKEN else {}
            )

            if response.status_code == 403:  # Rate limited
                logger.warning(f"GitHub rate limit hit for {username}")
                return None  # Graceful degradation

            return response.json() if response.status_code == 200 else None

    except Exception as e:
        logger.error(f"GitHub API error: {e}")
        return None
```

**Enrichment Queue with Throttling:**

```python
# oracle-ai-service/app/features/enrichment/queue.py

from celery import Celery
from datetime import timedelta

celery_app = Celery('enrichment')

@celery_app.task(
    rate_limit='100/h',  # Max 100 enrichments per hour
    retry_backoff=True,
    max_retries=3,
)
async def enrich_user_task(user_id: str, user_data: dict):
    """
    Celery task for profile enrichment with built-in rate limiting.
    """
    try:
        agent = create_enrichment_agent()
        result = await agent.ainvoke({
            "user_id": user_id,
            **user_data
        })

        # Handle result with fallback logic
        fallback_handler = EnrichmentFallbackHandler()
        await fallback_handler.handle_enrichment_result(user_id, result)

    except Exception as e:
        logger.error(f"Enrichment failed for {user_id}: {e}")
        # Mark as failed, will retry
        await mark_enrichment_failed(user_id, str(e))
        raise  # Celery will retry


# Batch enrichment for events (spread over time)
async def queue_event_enrichments(event_id: str):
    """Queue all attendees for enrichment, spread over time."""

    attendees = await get_unenriched_attendees(event_id)

    for i, attendee in enumerate(attendees):
        # Spread enrichments over 6 hours to avoid spikes
        delay = timedelta(seconds=i * 216)  # ~100 per hour

        enrich_user_task.apply_async(
            args=[attendee.id, attendee.to_dict()],
            countdown=delay.total_seconds()
        )

    logger.info(f"Queued {len(attendees)} enrichments for event {event_id}")
```

### 8.3 Cold Start & Graceful Degradation

**Event Size-Based Algorithm Switching:**

```python
# oracle-ai-service/app/features/recommendations/adaptive.py

class AdaptiveRecommendationEngine:
    """
    Adapts recommendation strategy based on event size and data quality.
    """

    async def generate_recommendations(
        self,
        user_id: str,
        event_id: str
    ) -> List[Recommendation]:
        """Generate recommendations with adaptive strategy."""

        attendees = await self.get_event_attendees(event_id)
        event_size = len(attendees)

        # Adapt strategy based on event size
        if event_size < 10:
            return await self._small_event_strategy(user_id, attendees)

        elif event_size < 50:
            return await self._medium_event_strategy(user_id, attendees)

        else:
            return await self._large_event_strategy(user_id, attendees)

    async def _small_event_strategy(
        self,
        user_id: str,
        attendees: List[Attendee]
    ) -> List[Recommendation]:
        """
        < 10 attendees: Too small for clustering.
        Strategy: Show everyone with basic goal matching.
        """

        user = await self.get_user(user_id)
        others = [a for a in attendees if a.id != user_id]

        recommendations = []
        for other in others:
            # Simple goal alignment scoring
            score = self._calculate_simple_match(user, other)

            recommendations.append(Recommendation(
                userId=other.id,
                matchScore=score,
                reasons=[self._generate_simple_reason(user, other)],
                conversationStarters=[
                    f"What brings you to {self.event.name}?",
                    f"I see you're in {other.industry} - how's that going?"
                ],
                strategy="small_event"
            ))

        # Sort by score, return all (small event = meet everyone)
        return sorted(recommendations, key=lambda r: r.matchScore, reverse=True)

    async def _medium_event_strategy(
        self,
        user_id: str,
        attendees: List[Attendee]
    ) -> List[Recommendation]:
        """
        10-50 attendees: Focus on goal alignment, skip complex clustering.
        Strategy: LLM-lite matching based on goals and interests.
        """

        user = await self.get_user(user_id)

        # Use a simpler, faster prompt
        prompt = self._build_medium_event_prompt(user, attendees)

        response = await self.llm.generate(
            prompt,
            model="claude-haiku",  # Faster, cheaper for medium events
            max_tokens=2000
        )

        return self._parse_recommendations(response)

    async def _large_event_strategy(
        self,
        user_id: str,
        attendees: List[Attendee]
    ) -> List[Recommendation]:
        """
        50+ attendees: Full LLM clustering with enriched profiles.
        Strategy: Use the full recommendation engine.
        """

        # This is the existing MatchmakingService logic
        service = MatchmakingService(self.llm, self.prisma)
        return await service.generate_recommendations(user_id, self.event_id)

    def _calculate_simple_match(self, user: User, other: User) -> int:
        """Simple matching for small events."""
        score = 50  # Base score

        # Goal alignment
        user_goals = set(user.goals)
        other_goals = set(other.goals)

        # Complementary goals (HIRE <-> GET_HIRED, etc.)
        complementary = {
            ("HIRE", "GET_HIRED"), ("GET_HIRED", "HIRE"),
            ("MENTOR", "GET_MENTORED"), ("GET_MENTORED", "MENTOR"),
            ("SELL", "BUY"), ("BUY", "SELL"),
            ("FIND_INVESTORS", "FIND_PARTNERS"),
        }

        for goal_pair in complementary:
            if goal_pair[0] in user_goals and goal_pair[1] in other_goals:
                score += 20

        # Shared interests
        shared_interests = set(user.interests) & set(other.interests)
        score += len(shared_interests) * 10

        # Same industry
        if user.industry == other.industry:
            score += 10

        return min(100, score)
```

**Huddle Cold Start Rules:**

```python
# oracle-ai-service/app/features/huddles/rules.py

class HuddleEligibilityChecker:
    """
    Determines if an event is eligible for huddles.
    """

    MIN_ATTENDEES_FOR_HUDDLES = 50
    MIN_ATTENDEES_FOR_PROBLEM_HUDDLES = 30
    MIN_CLUSTER_SIZE = 3

    async def can_generate_huddles(self, event_id: str) -> HuddleEligibility:
        """Check if event can support huddles."""

        attendee_count = await self.get_attendee_count(event_id)

        if attendee_count < self.MIN_ATTENDEES_FOR_PROBLEM_HUDDLES:
            return HuddleEligibility(
                eligible=False,
                reason="too_few_attendees",
                message=f"Huddles require at least {self.MIN_ATTENDEES_FOR_PROBLEM_HUDDLES} attendees",
                alternative="Focus on 1:1 recommendations instead"
            )

        if attendee_count < self.MIN_ATTENDEES_FOR_HUDDLES:
            return HuddleEligibility(
                eligible=True,
                huddle_types=["problem_based"],  # Only problem-based, not session/proximity
                message="Limited huddle support for medium-sized events"
            )

        return HuddleEligibility(
            eligible=True,
            huddle_types=["problem_based", "session_based", "proximity_based"],
            message="Full huddle support available"
        )
```

---

## Phase 9: Organizer Analytics Dashboard

> **The Problem:** Organizers need to prove ROI to their stakeholders. They need visibility into whether networking features are actually working.

### 9.1 Analytics Data Model

```prisma
model NetworkingAnalytics {
  id              String   @id @default(cuid())
  eventId         String   @unique

  // Computed daily
  computedAt      DateTime @default(now())

  // Registration metrics
  totalAttendees  Int
  profilesEnriched Int
  enrichmentRate  Float    // % who opted in and succeeded

  // Engagement metrics
  recommendationsGenerated Int
  recommendationsViewed    Int
  recommendationViewRate   Float

  // Connection metrics
  totalPings      Int
  totalDMs        Int
  totalConnections Int
  connectionsPerAttendee Float

  // Huddle metrics
  huddlesFormed   Int
  huddleInvitesSent Int
  huddleAcceptRate Float
  huddleAttendRate Float
  avgHuddleSize   Float

  // Quality metrics
  followUpsSent   Int
  followUpResponseRate Float

  // Top matching factors
  topInterests    Json     // [{interest: "AI/ML", count: 45}, ...]
  topGoalPairs    Json     // [{pair: ["HIRE", "GET_HIRED"], count: 23}, ...]

  event           Event    @relation(fields: [eventId], references: [id])
}
```

### 9.2 Analytics Computation Service

```python
# oracle-ai-service/app/features/analytics/compute.py

class NetworkingAnalyticsService:
    """
    Computes networking engagement metrics for organizer dashboard.
    """

    async def compute_event_analytics(self, event_id: str) -> NetworkingAnalytics:
        """Compute all networking metrics for an event."""

        # Get base counts
        attendees = await self.get_event_attendees(event_id)
        total_attendees = len(attendees)

        # Enrichment metrics
        enriched = [a for a in attendees if a.profile.enrichmentStatus == "COMPLETED"]
        opted_in = [a for a in attendees if a.profile.enrichmentStatus != "OPTED_OUT"]
        enrichment_rate = len(enriched) / len(opted_in) if opted_in else 0

        # Recommendation metrics
        recommendations = await self.get_event_recommendations(event_id)
        viewed = [r for r in recommendations if r.viewed]
        view_rate = len(viewed) / len(recommendations) if recommendations else 0

        # Connection metrics
        connections = await self.get_event_connections(event_id)
        pings = await self.get_event_pings(event_id)
        dms = await self.get_event_dms(event_id)

        connections_per_attendee = len(connections) / total_attendees if total_attendees else 0

        # Huddle metrics
        huddles = await self.get_event_huddles(event_id)
        huddle_invites = await self.get_huddle_invites(event_id)
        accepted_invites = [i for i in huddle_invites if i.status == "ACCEPTED"]
        attended = [i for i in huddle_invites if i.status == "ATTENDED"]

        huddle_accept_rate = len(accepted_invites) / len(huddle_invites) if huddle_invites else 0
        huddle_attend_rate = len(attended) / len(accepted_invites) if accepted_invites else 0

        avg_huddle_size = sum(h.participant_count for h in huddles) / len(huddles) if huddles else 0

        # Follow-up metrics
        follow_ups = await self.get_event_follow_ups(event_id)
        responded = [f for f in follow_ups if f.response_status == "RESPONDED"]
        follow_up_response_rate = len(responded) / len(follow_ups) if follow_ups else 0

        # Top matching factors
        top_interests = await self.compute_top_interests(connections)
        top_goal_pairs = await self.compute_top_goal_pairs(connections)

        return NetworkingAnalytics(
            eventId=event_id,
            totalAttendees=total_attendees,
            profilesEnriched=len(enriched),
            enrichmentRate=enrichment_rate,
            recommendationsGenerated=len(recommendations),
            recommendationsViewed=len(viewed),
            recommendationViewRate=view_rate,
            totalPings=len(pings),
            totalDMs=len(dms),
            totalConnections=len(connections),
            connectionsPerAttendee=connections_per_attendee,
            huddlesFormed=len(huddles),
            huddleInvitesSent=len(huddle_invites),
            huddleAcceptRate=huddle_accept_rate,
            huddleAttendRate=huddle_attend_rate,
            avgHuddleSize=avg_huddle_size,
            followUpsSent=len(follow_ups),
            followUpResponseRate=follow_up_response_rate,
            topInterests=top_interests,
            topGoalPairs=top_goal_pairs,
        )

    async def compute_top_interests(self, connections: List[Connection]) -> List[dict]:
        """Find which interests led to the most connections."""

        interest_counts = {}

        for conn in connections:
            user1_interests = set(conn.user.interests)
            user2_interests = set(conn.connected_user.interests)
            shared = user1_interests & user2_interests

            for interest in shared:
                interest_counts[interest] = interest_counts.get(interest, 0) + 1

        sorted_interests = sorted(
            interest_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )

        return [{"interest": k, "count": v} for k, v in sorted_interests[:10]]

    async def compute_top_goal_pairs(self, connections: List[Connection]) -> List[dict]:
        """Find which goal combinations led to connections."""

        pair_counts = {}

        for conn in connections:
            user1_goals = conn.user.goals
            user2_goals = conn.connected_user.goals

            for g1 in user1_goals:
                for g2 in user2_goals:
                    pair = tuple(sorted([g1, g2]))
                    pair_counts[pair] = pair_counts.get(pair, 0) + 1

        sorted_pairs = sorted(
            pair_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )

        return [{"pair": list(k), "count": v} for k, v in sorted_pairs[:10]]
```

### 9.3 Organizer Dashboard UI

```tsx
// globalconnect/src/app/(organizer)/events/[eventId]/analytics/networking/page.tsx

"use client";

import { useNetworkingAnalytics } from "@/hooks/use-networking-analytics";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import {
  Users,
  Sparkles,
  MessageCircle,
  UserPlus,
  TrendingUp,
  Target,
} from "lucide-react";

export default function NetworkingAnalyticsPage({
  params,
}: {
  params: { eventId: string };
}) {
  const { analytics, isLoading } = useNetworkingAnalytics(params.eventId);

  if (isLoading) return <AnalyticsSkeleton />;

  return (
    <div className="container py-8 space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold">Networking Engagement Report</h1>
        <p className="text-muted-foreground">
          How attendees are connecting at your event
        </p>
      </div>

      {/* Key Metrics */}
      <div className="grid grid-cols-4 gap-4">
        <MetricCard
          icon={<Users className="h-5 w-5" />}
          label="Connections Made"
          value={analytics.totalConnections}
          subtext={`${analytics.connectionsPerAttendee.toFixed(1)} per attendee`}
          target={3}
          targetLabel="Target: 3+"
        />
        <MetricCard
          icon={<Sparkles className="h-5 w-5" />}
          label="Recommendation Views"
          value={`${(analytics.recommendationViewRate * 100).toFixed(0)}%`}
          subtext={`${analytics.recommendationsViewed} of ${analytics.recommendationsGenerated}`}
          target={50}
          targetLabel="Target: 50%+"
        />
        <MetricCard
          icon={<UserPlus className="h-5 w-5" />}
          label="Huddle Accept Rate"
          value={`${(analytics.huddleAcceptRate * 100).toFixed(0)}%`}
          subtext={`${analytics.huddlesFormed} huddles formed`}
          target={40}
          targetLabel="Target: 40%+"
        />
        <MetricCard
          icon={<MessageCircle className="h-5 w-5" />}
          label="Follow-up Response"
          value={`${(analytics.followUpResponseRate * 100).toFixed(0)}%`}
          subtext={`${analytics.followUpsSent} follow-ups sent`}
          target={30}
          targetLabel="Target: 30%+"
        />
      </div>

      {/* Detailed Breakdown */}
      <div className="grid grid-cols-2 gap-6">
        {/* Profile Enrichment */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Profile Enrichment</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex justify-between items-center">
              <span className="text-sm text-muted-foreground">
                Enriched Profiles
              </span>
              <span className="font-medium">
                {analytics.profilesEnriched} / {analytics.totalAttendees}
              </span>
            </div>
            <Progress
              value={analytics.enrichmentRate * 100}
              className="h-2"
            />
            <p className="text-xs text-muted-foreground">
              {(analytics.enrichmentRate * 100).toFixed(0)}% of opted-in users
              successfully enriched
            </p>
          </CardContent>
        </Card>

        {/* Huddle Performance */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Huddle Performance</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-2xl font-bold">{analytics.huddlesFormed}</p>
                <p className="text-sm text-muted-foreground">Huddles Formed</p>
              </div>
              <div>
                <p className="text-2xl font-bold">
                  {analytics.avgHuddleSize.toFixed(1)}
                </p>
                <p className="text-sm text-muted-foreground">Avg Size</p>
              </div>
            </div>
            <div className="space-y-2">
              <div className="flex justify-between text-sm">
                <span>Invite → Accept</span>
                <span>{(analytics.huddleAcceptRate * 100).toFixed(0)}%</span>
              </div>
              <Progress value={analytics.huddleAcceptRate * 100} className="h-2" />
            </div>
            <div className="space-y-2">
              <div className="flex justify-between text-sm">
                <span>Accept → Attend</span>
                <span>{(analytics.huddleAttendRate * 100).toFixed(0)}%</span>
              </div>
              <Progress value={analytics.huddleAttendRate * 100} className="h-2" />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Top Matching Factors */}
      <div className="grid grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Top Interests Driving Connections</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {analytics.topInterests.slice(0, 5).map((item, i) => (
                <div key={i} className="flex items-center justify-between">
                  <span className="text-sm">{item.interest}</span>
                  <div className="flex items-center gap-2">
                    <div className="w-32 h-2 bg-muted rounded-full overflow-hidden">
                      <div
                        className="h-full bg-primary"
                        style={{
                          width: `${(item.count / analytics.topInterests[0].count) * 100}%`,
                        }}
                      />
                    </div>
                    <span className="text-sm text-muted-foreground w-8">
                      {item.count}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Top Goal Combinations</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {analytics.topGoalPairs.slice(0, 5).map((item, i) => (
                <div key={i} className="flex items-center justify-between">
                  <span className="text-sm">
                    {formatGoalPair(item.pair)}
                  </span>
                  <div className="flex items-center gap-2">
                    <div className="w-32 h-2 bg-muted rounded-full overflow-hidden">
                      <div
                        className="h-full bg-amber-500"
                        style={{
                          width: `${(item.count / analytics.topGoalPairs[0].count) * 100}%`,
                        }}
                      />
                    </div>
                    <span className="text-sm text-muted-foreground w-8">
                      {item.count}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Benchmark Comparison */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <Target className="h-5 w-5" />
            Industry Benchmark Comparison
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-4 gap-8">
            <BenchmarkItem
              metric="Active Networking"
              yourValue={analytics.connectionsPerAttendee > 0 ?
                Math.min(100, (analytics.totalConnections / analytics.totalAttendees) * 33).toFixed(0) : "0"}
              industryAvg="5-10%"
              target="30%"
              isGood={analytics.connectionsPerAttendee >= 3}
            />
            <BenchmarkItem
              metric="Recommendation Engagement"
              yourValue={`${(analytics.recommendationViewRate * 100).toFixed(0)}%`}
              industryAvg="15%"
              target="50%"
              isGood={analytics.recommendationViewRate >= 0.5}
            />
            <BenchmarkItem
              metric="Follow-up Rate"
              yourValue={`${(analytics.followUpResponseRate * 100).toFixed(0)}%`}
              industryAvg="10%"
              target="30%"
              isGood={analytics.followUpResponseRate >= 0.3}
            />
            <BenchmarkItem
              metric="Huddle Participation"
              yourValue={`${(analytics.huddleAcceptRate * 100).toFixed(0)}%`}
              industryAvg="N/A"
              target="40%"
              isGood={analytics.huddleAcceptRate >= 0.4}
            />
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

const BenchmarkItem = ({
  metric,
  yourValue,
  industryAvg,
  target,
  isGood,
}: {
  metric: string;
  yourValue: string;
  industryAvg: string;
  target: string;
  isGood: boolean;
}) => (
  <div className="text-center">
    <p className="text-sm text-muted-foreground mb-2">{metric}</p>
    <p className={cn(
      "text-3xl font-bold",
      isGood ? "text-green-600" : "text-amber-600"
    )}>
      {yourValue}
    </p>
    <div className="mt-2 text-xs text-muted-foreground">
      <p>Industry: {industryAvg}</p>
      <p>Target: {target}</p>
    </div>
  </div>
);
```

### 9.4 Analytics API

```python
# api-gateway/src/analytics/analytics.controller.ts

@Controller('analytics')
@UseGuards(OrganizerGuard)
export class AnalyticsController {

  @Get('events/:eventId/networking')
  async getNetworkingAnalytics(
    @Param('eventId') eventId: string,
    @CurrentUser() user: User,
  ) {
    // Verify user is organizer of this event
    await this.eventService.verifyOrganizer(eventId, user.id);

    // Get or compute analytics
    let analytics = await this.analyticsService.getCachedAnalytics(eventId);

    if (!analytics || this.isStale(analytics.computedAt)) {
      analytics = await this.oracleClient.post(
        `/analytics/compute/${eventId}`
      );
    }

    return analytics;
  }

  @Get('events/:eventId/networking/export')
  async exportNetworkingReport(
    @Param('eventId') eventId: string,
    @Query('format') format: 'pdf' | 'csv' = 'pdf',
  ) {
    const analytics = await this.getNetworkingAnalytics(eventId);

    if (format === 'csv') {
      return this.generateCSVReport(analytics);
    }

    return this.generatePDFReport(analytics);
  }
}
```

---

## Phase 10: Feedback & Learning

> **The Goal:** Continuously improve recommendation quality based on real outcomes. Know which matches worked and which didn't.

### 10.1 Post-Event Feedback Collection

```prisma
model ConnectionFeedback {
  id              String   @id @default(cuid())
  connectionId    String
  userId          String   // Who is giving feedback

  // Rating
  rating          Int      // 1-5 stars

  // Qualitative
  wasValuable     Boolean?
  willFollowUp    Boolean?
  wouldRecommend  Boolean?

  // What made it good/bad
  positiveFactors String[] // ["shared_interests", "goal_alignment", "good_conversation"]
  negativeFactors String[] // ["not_relevant", "awkward", "wrong_industry"]

  // Free text
  comments        String?

  createdAt       DateTime @default(now())

  connection      Connection @relation(fields: [connectionId], references: [id])

  @@unique([connectionId, userId])
}

model RecommendationFeedback {
  id                String   @id @default(cuid())
  recommendationId  String
  userId            String

  // Did they act on it?
  action            RecommendationAction

  // If they connected, how was it?
  connectionRating  Int?     // 1-5

  // Why did they skip?
  skipReason        String?  // "not_relevant", "already_know", "too_busy", etc.

  createdAt         DateTime @default(now())

  @@unique([recommendationId, userId])
}

enum RecommendationAction {
  VIEWED
  PINGED
  MESSAGED
  CONNECTED
  SKIPPED
  IGNORED
}
```

### 10.2 Feedback Collection UI

```tsx
// globalconnect/src/components/features/feedback/connection-feedback-modal.tsx

interface ConnectionFeedbackModalProps {
  connection: Connection;
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (feedback: ConnectionFeedbackData) => void;
}

export const ConnectionFeedbackModal = ({
  connection,
  isOpen,
  onClose,
  onSubmit,
}: ConnectionFeedbackModalProps) => {
  const [rating, setRating] = useState<number>(0);
  const [factors, setFactors] = useState<string[]>([]);
  const [willFollowUp, setWillFollowUp] = useState<boolean | null>(null);

  const positiveFactors = [
    { id: "shared_interests", label: "Shared interests" },
    { id: "goal_alignment", label: "Aligned goals" },
    { id: "good_conversation", label: "Great conversation" },
    { id: "valuable_insights", label: "Valuable insights" },
    { id: "potential_collaboration", label: "Potential collaboration" },
    { id: "career_opportunity", label: "Career opportunity" },
  ];

  const negativeFactors = [
    { id: "not_relevant", label: "Not relevant to my goals" },
    { id: "wrong_industry", label: "Different industry" },
    { id: "awkward_interaction", label: "Awkward interaction" },
    { id: "no_common_ground", label: "No common ground" },
    { id: "already_knew", label: "Already knew them" },
  ];

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>How was your connection?</DialogTitle>
          <DialogDescription>
            Your feedback helps us make better recommendations
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-6 py-4">
          {/* Person info */}
          <div className="flex items-center gap-3">
            <Avatar className="h-12 w-12">
              <AvatarImage src={connection.connectedUser.avatarUrl} />
              <AvatarFallback>
                {connection.connectedUser.name.split(" ").map(n => n[0]).join("")}
              </AvatarFallback>
            </Avatar>
            <div>
              <p className="font-medium">{connection.connectedUser.name}</p>
              <p className="text-sm text-muted-foreground">
                {connection.connectedUser.role} at {connection.connectedUser.company}
              </p>
            </div>
          </div>

          {/* Star Rating */}
          <div className="space-y-2">
            <label className="text-sm font-medium">
              How valuable was this connection?
            </label>
            <div className="flex gap-1">
              {[1, 2, 3, 4, 5].map((star) => (
                <button
                  key={star}
                  onClick={() => setRating(star)}
                  className="p-1"
                >
                  <Star
                    className={cn(
                      "h-8 w-8",
                      star <= rating
                        ? "fill-amber-400 text-amber-400"
                        : "text-muted-foreground"
                    )}
                  />
                </button>
              ))}
            </div>
            <p className="text-xs text-muted-foreground">
              {rating === 1 && "Not valuable"}
              {rating === 2 && "Slightly valuable"}
              {rating === 3 && "Moderately valuable"}
              {rating === 4 && "Very valuable"}
              {rating === 5 && "Extremely valuable - staying in touch!"}
            </p>
          </div>

          {/* Factors */}
          {rating > 0 && (
            <div className="space-y-2">
              <label className="text-sm font-medium">
                {rating >= 3 ? "What made it good?" : "What could have been better?"}
              </label>
              <div className="flex flex-wrap gap-2">
                {(rating >= 3 ? positiveFactors : negativeFactors).map((factor) => (
                  <Badge
                    key={factor.id}
                    variant={factors.includes(factor.id) ? "default" : "outline"}
                    className="cursor-pointer"
                    onClick={() => {
                      setFactors(
                        factors.includes(factor.id)
                          ? factors.filter((f) => f !== factor.id)
                          : [...factors, factor.id]
                      );
                    }}
                  >
                    {factor.label}
                  </Badge>
                ))}
              </div>
            </div>
          )}

          {/* Follow-up intent */}
          {rating >= 3 && (
            <div className="space-y-2">
              <label className="text-sm font-medium">
                Will you stay in touch?
              </label>
              <div className="flex gap-2">
                <Button
                  variant={willFollowUp === true ? "default" : "outline"}
                  size="sm"
                  onClick={() => setWillFollowUp(true)}
                >
                  Yes, definitely
                </Button>
                <Button
                  variant={willFollowUp === false ? "default" : "outline"}
                  size="sm"
                  onClick={() => setWillFollowUp(false)}
                >
                  Probably not
                </Button>
              </div>
            </div>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Skip
          </Button>
          <Button
            onClick={() => {
              onSubmit({
                connectionId: connection.id,
                rating,
                factors,
                willFollowUp,
              });
              onClose();
            }}
            disabled={rating === 0}
          >
            Submit Feedback
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
```

### 10.3 Post-Event Feedback Campaign

```typescript
// api-gateway/src/feedback/feedback.service.ts

@Injectable()
export class FeedbackService {

  /**
   * Trigger feedback collection 24 hours after event ends.
   */
  @Cron('0 10 * * *') // 10 AM daily
  async triggerPostEventFeedback() {
    // Find events that ended 24-48 hours ago
    const recentlyEndedEvents = await this.eventService.findMany({
      where: {
        endDate: {
          gte: subHours(new Date(), 48),
          lte: subHours(new Date(), 24),
        },
        feedbackCampaignSent: false,
      },
    });

    for (const event of recentlyEndedEvents) {
      await this.sendFeedbackCampaign(event.id);
    }
  }

  async sendFeedbackCampaign(eventId: string) {
    const attendees = await this.getAttendeesWithConnections(eventId);

    for (const attendee of attendees) {
      if (attendee.connections.length === 0) continue;

      // Send push notification
      await this.notificationService.send(attendee.userId, {
        type: 'feedback_request',
        title: 'How were your connections?',
        body: `You met ${attendee.connections.length} people at ${event.name}. Quick feedback helps us improve.`,
        action: {
          type: 'open_feedback',
          eventId,
        },
      });

      // Also send email for higher response rate
      await this.emailService.send(attendee.email, {
        template: 'feedback_request',
        data: {
          eventName: event.name,
          connectionCount: attendee.connections.length,
          topConnections: attendee.connections.slice(0, 3),
          feedbackUrl: `${APP_URL}/feedback/${eventId}`,
        },
      });
    }

    // Mark campaign as sent
    await this.eventService.update(eventId, {
      feedbackCampaignSent: true,
    });
  }
}
```

### 10.4 Feedback Analysis & Prompt Improvement

```python
# oracle-ai-service/app/features/feedback/analyzer.py

class FeedbackAnalyzer:
    """
    Analyzes connection feedback to improve recommendation quality.
    """

    async def analyze_recommendation_performance(
        self,
        event_id: str
    ) -> RecommendationAnalysis:
        """Analyze how well recommendations performed."""

        # Get all recommendations and their outcomes
        recommendations = await self.get_recommendations_with_feedback(event_id)

        # Calculate metrics by match score bands
        score_bands = self._group_by_score_bands(recommendations)

        # Analyze which factors predicted good connections
        factor_analysis = await self._analyze_success_factors(recommendations)

        # Identify patterns in failures
        failure_patterns = await self._analyze_failure_patterns(recommendations)

        return RecommendationAnalysis(
            total_recommendations=len(recommendations),
            acted_upon=len([r for r in recommendations if r.action != 'IGNORED']),
            connected=len([r for r in recommendations if r.action == 'CONNECTED']),
            avg_rating=self._avg_rating(recommendations),
            score_band_performance=score_bands,
            success_factors=factor_analysis,
            failure_patterns=failure_patterns,
        )

    def _group_by_score_bands(
        self,
        recommendations: List[RecommendationWithFeedback]
    ) -> dict:
        """Group recommendations by score and analyze performance."""

        bands = {
            "90-100": [],
            "80-89": [],
            "70-79": [],
            "60-69": [],
            "below_60": [],
        }

        for rec in recommendations:
            if rec.matchScore >= 90:
                bands["90-100"].append(rec)
            elif rec.matchScore >= 80:
                bands["80-89"].append(rec)
            elif rec.matchScore >= 70:
                bands["70-79"].append(rec)
            elif rec.matchScore >= 60:
                bands["60-69"].append(rec)
            else:
                bands["below_60"].append(rec)

        return {
            band: {
                "count": len(recs),
                "connection_rate": len([r for r in recs if r.action == 'CONNECTED']) / len(recs) if recs else 0,
                "avg_rating": sum(r.connectionRating or 0 for r in recs) / len([r for r in recs if r.connectionRating]) if any(r.connectionRating for r in recs) else 0,
            }
            for band, recs in bands.items()
        }

    async def _analyze_success_factors(
        self,
        recommendations: List[RecommendationWithFeedback]
    ) -> List[dict]:
        """Identify which factors correlate with successful connections."""

        successful = [r for r in recommendations if r.connectionRating and r.connectionRating >= 4]
        unsuccessful = [r for r in recommendations if r.connectionRating and r.connectionRating <= 2]

        factors_in_success = self._extract_factors(successful)
        factors_in_failure = self._extract_factors(unsuccessful)

        # Calculate which factors are over-represented in successes
        success_factor_rates = {}
        for factor, count in factors_in_success.items():
            success_rate = count / len(successful) if successful else 0
            failure_rate = factors_in_failure.get(factor, 0) / len(unsuccessful) if unsuccessful else 0

            success_factor_rates[factor] = {
                "success_rate": success_rate,
                "failure_rate": failure_rate,
                "lift": success_rate / failure_rate if failure_rate > 0 else float('inf'),
            }

        # Sort by lift (how much more common in successes vs failures)
        sorted_factors = sorted(
            success_factor_rates.items(),
            key=lambda x: x[1]["lift"],
            reverse=True
        )

        return [{"factor": k, **v} for k, v in sorted_factors[:10]]

    async def generate_prompt_improvement_suggestions(
        self,
        analysis: RecommendationAnalysis
    ) -> List[str]:
        """Generate suggestions for improving the recommendation prompt."""

        suggestions = []

        # Check if high-scored recommendations are converting
        high_score_band = analysis.score_band_performance.get("90-100", {})
        if high_score_band.get("connection_rate", 0) < 0.3:
            suggestions.append(
                "High-scored recommendations (90-100) have low conversion. "
                "Consider recalibrating score thresholds or adding more factors."
            )

        # Check for successful factors to emphasize
        top_success_factors = analysis.success_factors[:3]
        if top_success_factors:
            factor_names = [f["factor"] for f in top_success_factors]
            suggestions.append(
                f"Emphasize these factors in the prompt: {', '.join(factor_names)}. "
                "They correlate strongly with successful connections."
            )

        # Check for failure patterns to avoid
        if analysis.failure_patterns:
            pattern_names = [p["pattern"] for p in analysis.failure_patterns[:3]]
            suggestions.append(
                f"Avoid these patterns: {', '.join(pattern_names)}. "
                "They correlate with poor feedback."
            )

        return suggestions
```

### 10.5 A/B Testing Framework for Prompts

```python
# oracle-ai-service/app/features/recommendations/ab_testing.py

class PromptABTestingService:
    """
    A/B test different recommendation prompts to optimize quality.
    """

    # Define prompt variants
    PROMPT_VARIANTS = {
        "control": {
            "id": "control_v1",
            "description": "Original prompt - balanced approach",
            "weight": 0.5,  # 50% of traffic
        },
        "goal_focused": {
            "id": "goal_focused_v1",
            "description": "Prioritize goal alignment over interest overlap",
            "weight": 0.25,
        },
        "conversation_optimized": {
            "id": "conversation_v1",
            "description": "Emphasize conversation starters quality",
            "weight": 0.25,
        },
    }

    async def get_prompt_variant(self, user_id: str) -> str:
        """Deterministically assign user to a prompt variant."""

        # Hash user_id to get consistent assignment
        hash_value = int(hashlib.md5(user_id.encode()).hexdigest(), 16)

        # Use hash to pick variant based on weights
        cumulative = 0
        threshold = hash_value % 100 / 100

        for variant_name, variant in self.PROMPT_VARIANTS.items():
            cumulative += variant["weight"]
            if threshold < cumulative:
                return variant_name

        return "control"

    def get_prompt_for_variant(self, variant: str, user: dict, attendees: List[dict]) -> str:
        """Get the prompt template for a given variant."""

        if variant == "goal_focused":
            return self._build_goal_focused_prompt(user, attendees)
        elif variant == "conversation_optimized":
            return self._build_conversation_prompt(user, attendees)
        else:
            return self._build_control_prompt(user, attendees)

    def _build_goal_focused_prompt(self, user: dict, attendees: List[dict]) -> str:
        """Variant that emphasizes goal alignment."""

        return f"""You are an expert networking matchmaker. Your PRIMARY task is to find goal-aligned matches.

## CRITICAL: Goal Alignment is #1 Priority

Match these goal pairs with HIGH scores:
- HIRE + GET_HIRED (hiring manager + job seeker)
- MENTOR + GET_MENTORED (experienced + learning)
- SELL + BUY (vendor + buyer)
- FIND_INVESTORS + FIND_PARTNERS (founders + investors)

## The Attendee

**Name:** {user['name']}
**Goals:** {', '.join(user.get('goals', []))}
**Role:** {user['role']} at {user['company']}

## Scoring Rules

- Goal alignment: +40 points (base: 50)
- Same industry: +15 points
- Shared interests: +5 points each (max 20)
- Seniority fit: +10 points

Only return matches with 70+ final score.

{self._format_attendees(attendees)}

Return JSON array with top 10 recommendations.
"""

    async def track_variant_performance(
        self,
        variant: str,
        user_id: str,
        event_id: str,
        recommendation_id: str
    ):
        """Track which variant generated this recommendation."""

        await self.prisma.recommendationExperiment.create({
            "variant": variant,
            "userId": user_id,
            "eventId": event_id,
            "recommendationId": recommendation_id,
            "createdAt": datetime.utcnow(),
        })

    async def analyze_variant_performance(self) -> dict:
        """Analyze performance of each prompt variant."""

        results = {}

        for variant_name in self.PROMPT_VARIANTS.keys():
            recommendations = await self.get_recommendations_for_variant(variant_name)

            with_feedback = [r for r in recommendations if r.feedback]

            results[variant_name] = {
                "total": len(recommendations),
                "with_feedback": len(with_feedback),
                "avg_rating": sum(r.feedback.rating for r in with_feedback) / len(with_feedback) if with_feedback else 0,
                "connection_rate": len([r for r in recommendations if r.action == 'CONNECTED']) / len(recommendations) if recommendations else 0,
                "skip_rate": len([r for r in recommendations if r.action == 'SKIPPED']) / len(recommendations) if recommendations else 0,
            }

        return results
```

### 10.6 Feedback-Driven Prompt Updates

```python
# oracle-ai-service/app/features/recommendations/prompt_optimizer.py

class PromptOptimizer:
    """
    Uses feedback data to suggest prompt improvements.
    Run monthly to review and update prompts.
    """

    async def generate_monthly_report(self) -> PromptOptimizationReport:
        """Generate monthly prompt optimization report."""

        # Get last 30 days of feedback
        feedback = await self.get_recent_feedback(days=30)

        # Analyze A/B test results
        ab_results = await self.ab_testing.analyze_variant_performance()

        # Identify winning variant
        best_variant = max(
            ab_results.items(),
            key=lambda x: x[1]["avg_rating"]
        )

        # Get factor analysis
        factor_analysis = await self.feedback_analyzer.analyze_success_factors(feedback)

        # Generate recommendations
        recommendations = []

        # If a variant is significantly better
        if best_variant[1]["avg_rating"] > ab_results["control"]["avg_rating"] + 0.3:
            recommendations.append({
                "type": "promote_variant",
                "action": f"Promote '{best_variant[0]}' to 100% traffic",
                "reason": f"Rating {best_variant[1]['avg_rating']:.2f} vs control {ab_results['control']['avg_rating']:.2f}",
            })

        # If certain factors correlate with success
        high_lift_factors = [f for f in factor_analysis if f["lift"] > 2.0]
        if high_lift_factors:
            recommendations.append({
                "type": "emphasize_factors",
                "action": f"Add more weight to: {[f['factor'] for f in high_lift_factors]}",
                "reason": f"These factors have {high_lift_factors[0]['lift']:.1f}x higher success rate",
            })

        return PromptOptimizationReport(
            period="last_30_days",
            total_recommendations=len(feedback),
            avg_rating=sum(f.rating for f in feedback) / len(feedback) if feedback else 0,
            ab_test_results=ab_results,
            winning_variant=best_variant[0],
            factor_analysis=factor_analysis,
            recommendations=recommendations,
        )
```

---

## Environment Variables

Add to `.env`:

```bash
# Tavily API for web search
TAVILY_API_KEY=tvly-xxxxxxxxxxxxx

# LLM Provider (Anthropic recommended)
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxx
LLM_MODEL=claude-sonnet-4-20250514

# Optional: Rate limiting for enrichment
ENRICHMENT_RATE_LIMIT_PER_HOUR=100
RECOMMENDATION_RATE_LIMIT_PER_HOUR=500
```

---

## Phase 11: Data Privacy & GDPR Compliance

This phase ensures the matchmaking system complies with GDPR, CCPA, and other data protection regulations.

### 11.1 Data Retention Policies

**Retention Schedule:**

| Data Type | Retention Period | Justification |
|-----------|------------------|---------------|
| Enriched profile data | 2 years after last event | Legitimate business interest |
| Recommendation history | 1 year | Performance analytics |
| Connection activity | Indefinite (user-owned) | Part of user's network |
| Search/enrichment logs | 90 days | Debugging only |
| Deleted user data | 30 days (soft delete) | Recovery window |

**Automated Cleanup Service:**

```python
# oracle-ai-service/app/tasks/data_retention.py

from celery import shared_task
from datetime import datetime, timedelta
from app.db import prisma

@shared_task
def cleanup_expired_data():
    """
    Daily task to enforce data retention policies.
    Runs at 3 AM UTC.
    """
    now = datetime.utcnow()

    # 1. Delete enrichment logs older than 90 days
    enrichment_cutoff = now - timedelta(days=90)
    await prisma.enrichmentlog.delete_many(
        where={"createdAt": {"lt": enrichment_cutoff}}
    )

    # 2. Anonymize recommendations older than 1 year
    recommendation_cutoff = now - timedelta(days=365)
    await prisma.recommendation.update_many(
        where={
            "createdAt": {"lt": recommendation_cutoff},
            "anonymized": False
        },
        data={
            "anonymized": True,
            "matchReason": "[Retained for analytics only]",
            # Keep score for aggregate analytics, remove PII
        }
    )

    # 3. Hard delete soft-deleted users after 30 days
    deletion_cutoff = now - timedelta(days=30)
    await hard_delete_users(deletion_cutoff)

    # 4. Purge enriched data for users inactive > 2 years
    inactive_cutoff = now - timedelta(days=730)
    await prisma.userprofile.update_many(
        where={
            "user": {"lastActiveAt": {"lt": inactive_cutoff}},
            "enrichedData": {"not": None}
        },
        data={
            "enrichedData": None,
            "linkedinData": None,
            "githubData": None,
            "twitterData": None,
            "enrichmentStatus": "PURGED_INACTIVE"
        }
    )

    logger.info(f"Data retention cleanup completed at {now}")


async def hard_delete_users(cutoff: datetime):
    """
    Permanently delete users who requested deletion 30+ days ago.
    Cascades to all related data.
    """
    users_to_delete = await prisma.user.find_many(
        where={
            "deletedAt": {"lt": cutoff},
            "deletedAt": {"not": None}
        }
    )

    for user in users_to_delete:
        await prisma.$transaction([
            # Delete in dependency order
            prisma.connectionactivity.delete_many(
                where={"connection": {"userId": user.id}}
            ),
            prisma.connection.delete_many(
                where={"OR": [{"userId": user.id}, {"connectedUserId": user.id}]}
            ),
            prisma.recommendation.delete_many(
                where={"OR": [{"userId": user.id}, {"recommendedUserId": user.id}]}
            ),
            prisma.huddleparticipant.delete_many(
                where={"userId": user.id}
            ),
            prisma.userprofile.delete(where={"userId": user.id}),
            prisma.user.delete(where={"id": user.id}),
        ])

        logger.info(f"Hard deleted user {user.id}")
```

### 11.2 User Data Deletion Endpoints

**GDPR Article 17 - Right to Erasure:**

```python
# api-gateway/src/routes/privacy.py

from fastapi import APIRouter, Depends, HTTPException
from app.auth import get_current_user
from app.services.privacy import PrivacyService

router = APIRouter(prefix="/privacy", tags=["privacy"])

@router.post("/request-deletion")
async def request_account_deletion(
    current_user: User = Depends(get_current_user),
    privacy_service: PrivacyService = Depends()
):
    """
    Initiate account deletion (GDPR Article 17).
    - Immediate: Anonymize public-facing data
    - 30-day grace: User can cancel
    - After 30 days: Hard delete all data
    """
    await privacy_service.initiate_deletion(current_user.id)

    return {
        "status": "deletion_scheduled",
        "message": "Your account is scheduled for deletion in 30 days.",
        "cancellation_deadline": datetime.utcnow() + timedelta(days=30),
        "immediate_effects": [
            "Your profile is now hidden from other users",
            "You will no longer appear in recommendations",
            "Existing connections will see '[Deleted User]'"
        ]
    }


@router.post("/cancel-deletion")
async def cancel_deletion(
    current_user: User = Depends(get_current_user),
    privacy_service: PrivacyService = Depends()
):
    """Cancel a pending deletion request within 30-day window."""
    result = await privacy_service.cancel_deletion(current_user.id)

    if not result.success:
        raise HTTPException(400, "No pending deletion to cancel")

    return {"status": "deletion_cancelled", "message": "Your account has been restored."}


@router.get("/export-data")
async def export_user_data(
    current_user: User = Depends(get_current_user),
    privacy_service: PrivacyService = Depends()
):
    """
    GDPR Article 20 - Right to Data Portability.
    Returns all user data in machine-readable format.
    """
    export = await privacy_service.export_user_data(current_user.id)

    return {
        "exported_at": datetime.utcnow(),
        "format": "JSON",
        "data": {
            "profile": export.profile,
            "enriched_data": export.enriched_data,
            "connections": export.connections,
            "recommendations_received": export.recommendations,
            "huddles_participated": export.huddles,
            "activity_log": export.activity,
        }
    }


@router.get("/data-processing-info")
async def get_data_processing_info():
    """
    GDPR Article 13/14 - Information about processing.
    """
    return {
        "data_controller": "GlobalConnect Inc.",
        "contact": "privacy@globalconnect.example.com",
        "purposes": [
            {
                "purpose": "Profile enrichment",
                "legal_basis": "Consent (opt-in)",
                "data_categories": ["Name", "Company", "Public social profiles"],
                "retention": "2 years after last event attendance"
            },
            {
                "purpose": "Connection recommendations",
                "legal_basis": "Legitimate interest",
                "data_categories": ["Interests", "Goals", "Event attendance"],
                "retention": "1 year for history, indefinite for connections"
            },
            {
                "purpose": "Huddle facilitation",
                "legal_basis": "Contract performance",
                "data_categories": ["Location during event", "Huddle participation"],
                "retention": "Duration of event + 90 days"
            }
        ],
        "third_parties": [
            {"name": "Tavily", "purpose": "Web search for enrichment", "data_shared": "Name, company"},
            {"name": "Anthropic", "purpose": "AI recommendations", "data_shared": "Anonymized profiles"}
        ],
        "rights": [
            "Access your data (Article 15)",
            "Rectify inaccurate data (Article 16)",
            "Request deletion (Article 17)",
            "Export your data (Article 20)",
            "Object to processing (Article 21)"
        ]
    }
```

### 11.3 Audit Logging

**Comprehensive audit trail for compliance:**

```python
# oracle-ai-service/app/services/audit.py

from enum import Enum
from datetime import datetime
from app.db import prisma

class AuditAction(str, Enum):
    # Data access
    PROFILE_VIEWED = "profile_viewed"
    ENRICHMENT_ACCESSED = "enrichment_accessed"
    RECOMMENDATIONS_GENERATED = "recommendations_generated"

    # Data modification
    PROFILE_UPDATED = "profile_updated"
    ENRICHMENT_TRIGGERED = "enrichment_triggered"
    CONNECTION_CREATED = "connection_created"

    # Privacy actions
    DELETION_REQUESTED = "deletion_requested"
    DELETION_CANCELLED = "deletion_cancelled"
    DATA_EXPORTED = "data_exported"
    CONSENT_UPDATED = "consent_updated"

    # Admin actions
    ADMIN_DATA_ACCESS = "admin_data_access"
    DATA_RETENTION_CLEANUP = "data_retention_cleanup"


class AuditLogger:
    """GDPR-compliant audit logging service."""

    async def log(
        self,
        action: AuditAction,
        actor_id: str,
        target_user_id: str | None = None,
        metadata: dict | None = None,
        ip_address: str | None = None
    ):
        """
        Log an auditable action.
        Retention: 7 years (legal requirement for some jurisdictions)
        """
        await prisma.auditlog.create(
            data={
                "action": action.value,
                "actorId": actor_id,
                "targetUserId": target_user_id,
                "metadata": metadata or {},
                "ipAddress": self._hash_ip(ip_address),  # Store hashed for privacy
                "timestamp": datetime.utcnow(),
            }
        )

    def _hash_ip(self, ip: str | None) -> str | None:
        """Hash IP for privacy while maintaining audit capability."""
        if not ip:
            return None
        import hashlib
        # Use a daily salt so IPs can be correlated within a day
        daily_salt = datetime.utcnow().strftime("%Y-%m-%d")
        return hashlib.sha256(f"{ip}:{daily_salt}".encode()).hexdigest()[:16]


# Audit log schema
"""
model AuditLog {
  id           String   @id @default(cuid())
  action       String
  actorId      String   // Who performed the action
  targetUserId String?  // Whose data was affected (if applicable)
  metadata     Json     // Action-specific details
  ipAddress    String?  // Hashed IP
  timestamp    DateTime @default(now())

  @@index([actorId, timestamp])
  @@index([targetUserId, timestamp])
  @@index([action, timestamp])
}
"""
```

### 11.4 Consent Management

**Granular consent for enrichment features:**

```typescript
// globalconnect/src/components/features/privacy/consent-manager.tsx

interface ConsentSettings {
  profileEnrichment: boolean;     // Allow web search for profile data
  socialProfileLinking: boolean;  // Link to LinkedIn/GitHub/Twitter
  recommendationEmails: boolean;  // Receive recommendation notifications
  postEventFollowUp: boolean;     // Automated follow-up suggestions
  analyticsParticipation: boolean; // Include in aggregate analytics
}

export const ConsentManager = () => {
  const { data: consent, mutate } = useConsent();

  const updateConsent = async (key: keyof ConsentSettings, value: boolean) => {
    await api.patch('/privacy/consent', { [key]: value });

    // If disabling enrichment, trigger cleanup
    if (key === 'profileEnrichment' && !value) {
      await api.post('/privacy/clear-enrichment');
    }

    mutate();
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Privacy & Data Settings</CardTitle>
        <CardDescription>
          Control how your data is used. Changes take effect immediately.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <ConsentToggle
          label="Profile Enrichment"
          description="Allow us to search public sources (LinkedIn, GitHub) to enhance your profile and improve recommendations."
          checked={consent.profileEnrichment}
          onChange={(v) => updateConsent('profileEnrichment', v)}
        />
        <ConsentToggle
          label="Social Profile Linking"
          description="Display links to your social profiles on your networking card."
          checked={consent.socialProfileLinking}
          onChange={(v) => updateConsent('socialProfileLinking', v)}
        />
        <ConsentToggle
          label="Recommendation Notifications"
          description="Receive emails about new connection recommendations at events."
          checked={consent.recommendationEmails}
          onChange={(v) => updateConsent('recommendationEmails', v)}
        />
        <ConsentToggle
          label="Post-Event Follow-ups"
          description="Get automated suggestions for following up with people you met."
          checked={consent.postEventFollowUp}
          onChange={(v) => updateConsent('postEventFollowUp', v)}
        />

        <Separator />

        <div className="pt-4">
          <h4 className="font-medium text-destructive">Danger Zone</h4>
          <div className="mt-4 space-y-2">
            <Button variant="outline" onClick={handleExportData}>
              Export All My Data
            </Button>
            <Button variant="destructive" onClick={handleRequestDeletion}>
              Delete My Account
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};
```

### 11.5 LLM Data Handling

**Ensuring AI providers don't retain user data:**

```python
# oracle-ai-service/app/llm/privacy_wrapper.py

from anthropic import Anthropic

class PrivacyAwareAnthropicClient:
    """
    Wrapper that ensures user data sent to Anthropic is:
    1. Minimized (only necessary fields)
    2. Anonymized where possible
    3. Not used for training (via API headers)
    """

    def __init__(self):
        self.client = Anthropic(
            api_key=settings.ANTHROPIC_API_KEY,
            default_headers={
                # Request no data retention
                "anthropic-data-retention": "none",
            }
        )

    async def generate_recommendations(
        self,
        user_profile: dict,
        candidate_profiles: list[dict],
        prompt_template: str
    ) -> dict:
        """
        Generate recommendations with privacy-safe profile handling.
        """
        # Anonymize before sending to LLM
        anonymized_user = self._anonymize_profile(user_profile)
        anonymized_candidates = [
            self._anonymize_profile(c) for c in candidate_profiles
        ]

        response = await self.client.messages.create(
            model=settings.LLM_MODEL,
            max_tokens=1024,
            messages=[{
                "role": "user",
                "content": prompt_template.format(
                    user=anonymized_user,
                    candidates=anonymized_candidates
                )
            }]
        )

        return self._parse_response(response)

    def _anonymize_profile(self, profile: dict) -> dict:
        """
        Remove PII before sending to LLM.
        LLM only needs:
        - Interests, goals, seniority (for matching)
        - NOT: name, email, company (unless consented)
        """
        return {
            "id": profile.get("id"),  # Keep for mapping response back
            "interests": profile.get("interests", []),
            "goal": profile.get("goal"),
            "seniority": profile.get("seniority"),
            "function": profile.get("function"),
            # Include company only if user consented to enrichment
            "company": profile.get("company") if profile.get("enrichmentConsent") else "[Hidden]",
            # Never send to LLM
            # "name": EXCLUDED
            # "email": EXCLUDED
            # "socialUrls": EXCLUDED
        }
```

---

## Implementation Order

### Sprint 1: Foundation (Week 1)
1. Add database schema (UserProfile, Recommendation)
2. Update registration form with interests/goals
3. Create optional enrichment step
4. Basic API endpoints

### Sprint 2: Enrichment Agent (Week 2)
1. Set up LangGraph agent structure
2. Implement Tavily search integration
3. GitHub public API integration
4. Profile extraction and storage

### Sprint 3: Recommendation Engine (Week 3)
1. LLM prompt engineering
2. Recommendation generation service
3. Caching and expiration logic
4. API endpoints

### Sprint 4: Frontend (Week 4)
1. Recommendations panel component
2. Tabbed networking interface
3. useRecommendations hook
4. Polish and animations

### Sprint 5: Automation & Polish (Week 5)
1. Event check-in triggers
2. Daily cron jobs
3. Analytics tracking
4. Performance optimization

### Sprint 6: Facilitated Huddles (Week 6-7)
1. Huddle database schema and API
2. Problem statement in registration flow
3. Huddle generation logic (problem-based, session-based, proximity)
4. WebSocket invitation flow
5. Huddle invitation UI component
6. Huddle triggers and scheduling

### Sprint 7: Post-Event & Retention (Week 8-9)
1. Connection persistence schema and API
2. Follow-up suggestion generator (LLM-powered)
3. Follow-up reminder notifications
4. "Your Network" page with connection management
5. Cross-event discovery ("Connections attending")
6. Connection activity feed
7. Monthly digest emails
8. Retention trigger automation

### Sprint 8: Operational Resilience (Week 10)
1. Implement ProfileTier system and enrichment fallback logic
2. Add rate limiting for Tavily, GitHub, and LLM calls
3. Celery queue with throttling for batch enrichments
4. Profile completion banner UI for TIER_2/TIER_3 users
5. Adaptive recommendation engine (event size-based)
6. Huddle eligibility checker for cold start handling

### Sprint 9: Organizer Analytics (Week 11)
1. NetworkingAnalytics data model
2. Analytics computation service
3. Organizer dashboard UI with key metrics
4. Benchmark comparison component
5. Export functionality (PDF/CSV reports)
6. Analytics API endpoints

### Sprint 10: Feedback & Learning (Week 12-13)
1. ConnectionFeedback and RecommendationFeedback schemas
2. Post-event feedback collection UI (star ratings, factors)
3. Feedback campaign automation (24-48h after event)
4. Feedback analysis service (success factors, failure patterns)
5. Prompt A/B testing framework
6. Monthly prompt optimization reports

---

## Parallel Implementation Strategy

> **Goal:** Reduce implementation time from 13 weeks to ~6 weeks using 3 parallel agent/team tracks.

### Dependency Graph

```
                              Sprint 1: Foundation (BLOCKING)
                                         │
            ┌────────────────────────────┼────────────────────────────┐
            │                            │                            │
            ▼                            ▼                            ▼
    ┌───────────────┐           ┌───────────────┐           ┌───────────────┐
    │   TRACK A     │           │   TRACK B     │           │   TRACK C     │
    │  Backend/AI   │           │ Core Features │           │Social Features│
    └───────┬───────┘           └───────┬───────┘           └───────┬───────┘
            │                            │                            │
            ▼                            ▼                            ▼
      Sprint 2:                    Sprint 3:                    Sprint 6:
      Enrichment                   Recommendations              Huddles
            │                            │                            │
            ▼                            ▼                            │
      Sprint 8:                    Sprint 4:                          │
      Resilience                   Frontend ◄─────────────────────────┤
            │                            │                            │
            │                            ▼                            ▼
            │                      Sprint 5:                    Sprint 7:
            │                      Automation                   Retention
            │                            │                            │
            ▼                            ▼                            │
      Sprint 9:                    Sprint 10:                         │
      Analytics ◄────────────────────────┴────────────────────────────┘
```

### Parallel Timeline

| Week | Track A (Backend/AI) | Track B (Core Features) | Track C (Social) | Sync Points |
|------|---------------------|------------------------|------------------|-------------|
| **1** | Sprint 1: Foundation | Sprint 1: Foundation | Sprint 1: Foundation | All tracks collaborate |
| **2** | Sprint 2: Enrichment | Sprint 3: Recommendations | Sprint 6: Huddles | Schema freeze |
| **3** | Sprint 2 (cont.) | Sprint 3 (cont.) | Sprint 6 (cont.) | API contracts finalized |
| **4** | Sprint 8: Resilience | Sprint 4: Frontend | Sprint 7: Retention | Integration testing |
| **5** | Sprint 8 (cont.) | Sprint 5: Automation | Sprint 7 (cont.) | E2E testing begins |
| **6** | Sprint 9: Analytics | Sprint 10: Feedback | - | Final integration |

### Critical Sync Points

1. **End of Week 1 - Schema Freeze**
   - All database schemas must be finalized
   - No breaking changes to shared models after this point

2. **End of Week 2 - API Contracts**
   - All inter-service API contracts documented
   - OpenAPI specs for oracle-ai-service endpoints
   - WebSocket event schemas for real-time-service

3. **End of Week 4 - Integration Testing**
   - All tracks must have working endpoints
   - Cross-track integration tests begin

4. **Week 6 - Final Integration**
   - All features merged to main
   - Full E2E testing
   - Performance benchmarking

### Track Ownership

| Track | Services Owned | Key Deliverables |
|-------|---------------|------------------|
| **Track A** | oracle-ai-service | Enrichment agent, Rate limiting, Analytics computation |
| **Track B** | api-gateway, globalconnect | Recommendation API, Frontend components, Automation triggers |
| **Track C** | real-time-service, globalconnect | Huddles gateway, Retention features, WebSocket events |

### Shared Resources

All tracks share and must coordinate on:
- `shared-libs/prisma-client` - Database schemas
- `shared-libs/common` - DTOs, interfaces, utilities
- Integration tests in `e2e/`

---

## Cost Estimation

Per 1000 users at an event:

| Operation | Frequency | Est. Cost |
|-----------|-----------|-----------|
| Profile Enrichment (Tavily) | Once per user | ~$5-10 |
| Recommendation Generation (Claude) | Once per user/day | ~$20-40 |
| GitHub API | Once per user | Free |

**Total per event:** ~$25-50 per 1000 users

Much cheaper than real-time LLM calls which would be $500+ for the same users.

---

## Success Metrics

Track these to measure effectiveness:

1. **Enrichment Coverage:** % of users with enriched profiles
2. **Recommendation Views:** % of recommendations viewed
3. **Ping Rate:** % of recommendations that led to pings
4. **Connection Rate:** % of recommendations that led to DMs
5. **Match Score Accuracy:** Do high-scored matches convert better?
6. **User Satisfaction:** Post-event survey on networking quality

---

## Agent Implementation Prompts

> **Purpose:** These prompts are designed to be given to AI coding agents to implement each track. They include security requirements, optimization guidelines, and best practices that MUST be followed.

---

### AGENT PROMPT: Track A - Backend/AI Services

```markdown
# Track A: Backend/AI Services Implementation

You are implementing the AI-powered backend services for GlobalConnect's networking feature. Your track owns `oracle-ai-service` and is responsible for profile enrichment, rate limiting, and analytics.

## Your Sprints
- Sprint 2: Profile Enrichment Agent
- Sprint 8: Operational Resilience
- Sprint 9: Organizer Analytics

## Specification Reference
Read the full specification at: `AI_MATCHMAKING_SPEC.md`
Focus on: Phase 2, Phase 8, Phase 9

---

## CRITICAL REQUIREMENTS

### Security (NON-NEGOTIABLE)

1. **API Key Protection**
   - NEVER hardcode API keys (Tavily, Anthropic, GitHub)
   - Use environment variables via `pydantic-settings`
   - Validate all env vars on startup, fail fast if missing
   ```python
   class Settings(BaseSettings):
       TAVILY_API_KEY: str
       ANTHROPIC_API_KEY: str
       GITHUB_TOKEN: Optional[str] = None  # Optional but recommended

       model_config = SettingsConfigDict(env_file=".env")

   settings = Settings()  # Fails immediately if required vars missing
   ```

2. **Input Validation**
   - Validate ALL user inputs with Pydantic models
   - Sanitize user names before using in search queries (prevent injection)
   - Limit string lengths to prevent memory attacks
   ```python
   class EnrichmentRequest(BaseModel):
       user_id: str = Field(..., min_length=1, max_length=50, pattern=r'^[a-zA-Z0-9_-]+$')
       name: str = Field(..., min_length=1, max_length=200)
       company: str = Field(..., min_length=1, max_length=200)

       @field_validator('name', 'company')
       def sanitize_for_search(cls, v):
           # Remove special characters that could affect search
           return re.sub(r'[<>"\';(){}]', '', v).strip()
   ```

3. **Rate Limiting Security**
   - Implement per-user rate limits to prevent abuse
   - Log suspicious patterns (e.g., 100+ enrichment requests from same IP)
   - Add circuit breakers for external APIs

4. **Data Privacy**
   - Only store publicly available information
   - Implement data retention policies (delete enrichment data after 1 year)
   - Add audit logging for all enrichment operations
   ```python
   async def log_enrichment_audit(user_id: str, sources_accessed: List[str], success: bool):
       await prisma.enrichmentauditlog.create(data={
           "userId": user_id,
           "sourcesAccessed": sources_accessed,
           "success": success,
           "timestamp": datetime.utcnow(),
           "ipAddress": get_client_ip(),  # For abuse detection
       })
   ```

### Performance Optimization

1. **Async Everywhere**
   - ALL I/O operations must be async
   - Use `asyncio.gather()` for parallel API calls
   ```python
   # GOOD: Parallel searches
   linkedin, github, twitter = await asyncio.gather(
       search_linkedin(user),
       search_github(user),
       search_twitter(user),
       return_exceptions=True  # Don't fail all if one fails
   )

   # BAD: Sequential searches
   linkedin = await search_linkedin(user)
   github = await search_github(user)
   ```

2. **Connection Pooling**
   - Reuse HTTP clients, don't create per-request
   ```python
   # Module-level client with connection pooling
   http_client = httpx.AsyncClient(
       timeout=30.0,
       limits=httpx.Limits(max_connections=100, max_keepalive_connections=20)
   )

   # Cleanup on shutdown
   @app.on_event("shutdown")
   async def shutdown():
       await http_client.aclose()
   ```

3. **Caching Strategy**
   - Cache Tavily search results for 24 hours (same query = same results)
   - Cache GitHub profiles for 7 days (they don't change often)
   - Use Redis with TTL
   ```python
   async def get_cached_or_fetch(cache_key: str, fetch_fn, ttl_seconds: int):
       cached = await redis.get(cache_key)
       if cached:
           return json.loads(cached)

       result = await fetch_fn()
       await redis.setex(cache_key, ttl_seconds, json.dumps(result))
       return result
   ```

4. **Background Processing**
   - Enrichment MUST run in background (Celery/ARQ)
   - Never block HTTP requests on enrichment
   - Use job queues with priority levels

### Code Quality

1. **Type Hints Required**
   - ALL functions must have complete type hints
   - Use `TypedDict` for complex dictionaries
   - Run `mypy --strict` in CI

2. **Error Handling**
   - Create custom exception hierarchy
   - Never expose internal errors to users
   - Log full stack traces, return safe messages
   ```python
   class EnrichmentError(Exception):
       """Base exception for enrichment errors."""
       pass

   class ExternalAPIError(EnrichmentError):
       """External API (Tavily, GitHub) failed."""
       def __init__(self, service: str, status_code: int, message: str):
           self.service = service
           self.status_code = status_code
           super().__init__(f"{service} API error: {status_code}")

   class RateLimitExceeded(EnrichmentError):
       """Rate limit exceeded for user or globally."""
       pass
   ```

3. **Testing Requirements**
   - Unit tests for all business logic (pytest)
   - Integration tests for API endpoints
   - Mock external APIs in tests
   - Minimum 80% code coverage
   ```python
   # tests/test_enrichment.py
   @pytest.fixture
   def mock_tavily():
       with patch('app.services.tavily_client') as mock:
           mock.search.return_value = {"results": [...]}
           yield mock

   async def test_enrichment_handles_api_failure(mock_tavily):
       mock_tavily.search.side_effect = httpx.TimeoutException("timeout")
       result = await enrich_profile(user_id="123", name="Test User")
       assert result.status == "FAILED"
       assert result.tier == ProfileTier.TIER_3_MANUAL
   ```

4. **Documentation**
   - Docstrings for all public functions
   - OpenAPI documentation for all endpoints
   - Architecture decision records (ADRs) for major choices

### File Structure

```
oracle-ai-service/
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI app setup
│   ├── config.py                  # Settings, env vars
│   ├── dependencies.py            # Dependency injection
│   ├── core/
│   │   ├── rate_limiter.py       # Token bucket implementation
│   │   ├── cache.py              # Redis caching utilities
│   │   ├── security.py           # Input sanitization
│   │   └── exceptions.py         # Custom exceptions
│   ├── features/
│   │   ├── enrichment/
│   │   │   ├── agent.py          # LangGraph agent
│   │   │   ├── nodes/            # Agent nodes
│   │   │   ├── fallback.py       # Tier fallback logic
│   │   │   ├── router.py         # API endpoints
│   │   │   └── schemas.py        # Pydantic models
│   │   ├── analytics/
│   │   │   ├── compute.py        # Analytics computation
│   │   │   ├── router.py
│   │   │   └── schemas.py
│   │   └── recommendations/
│   │       └── ... (Track B owns this)
│   └── services/
│       ├── tavily.py             # Tavily client wrapper
│       ├── github.py             # GitHub API client
│       └── llm.py                # Anthropic client wrapper
├── tests/
│   ├── unit/
│   ├── integration/
│   └── conftest.py
├── Dockerfile
├── requirements.txt
└── pyproject.toml
```

### Deliverables Checklist

Sprint 2:
- [ ] LangGraph enrichment agent with all extraction nodes
- [ ] Tavily search integration with caching
- [ ] GitHub public API integration
- [ ] Profile tier assignment logic
- [ ] Background job queue setup
- [ ] Enrichment API endpoints
- [ ] Unit tests (80%+ coverage)

Sprint 8:
- [ ] Rate limiter implementation (token bucket)
- [ ] Per-user rate limit tracking
- [ ] Celery queue with throttling
- [ ] Circuit breakers for external APIs
- [ ] Fallback handler for enrichment failures
- [ ] Profile completion notification triggers

Sprint 9:
- [ ] NetworkingAnalytics computation service
- [ ] Top interests/goals analysis
- [ ] Analytics caching (compute once per hour)
- [ ] Export functionality (JSON for API)
- [ ] Analytics API endpoints

### Commands to Run

```bash
# Setup
cd oracle-ai-service
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Development
uvicorn app.main:app --reload --port 8001

# Testing
pytest --cov=app --cov-report=html
mypy app --strict

# Linting
ruff check app
black app --check
```

## START IMPLEMENTATION

Begin with Sprint 2, Phase 2 of the specification. Create the enrichment agent first, then build the API endpoints around it.
```

---

### AGENT PROMPT: Track B - Core Features

```markdown
# Track B: Core Features Implementation

You are implementing the core recommendation and frontend features for GlobalConnect's networking system. Your track owns `api-gateway` routes, `globalconnect` frontend, and orchestration logic.

## Your Sprints
- Sprint 3: LLM Recommendation Engine
- Sprint 4: Frontend Integration
- Sprint 5: Triggers & Automation
- Sprint 10: Feedback & Learning

## Specification Reference
Read the full specification at: `AI_MATCHMAKING_SPEC.md`
Focus on: Phase 3, Phase 4, Phase 5, Phase 10

---

## CRITICAL REQUIREMENTS

### Security (NON-NEGOTIABLE)

1. **Authentication & Authorization**
   - ALL recommendation endpoints require authentication
   - Users can ONLY access their own recommendations
   - Implement proper RBAC for admin endpoints
   ```typescript
   // api-gateway/src/recommendations/recommendations.controller.ts
   @Get(':eventId/for/:userId')
   @UseGuards(JwtAuthGuard)
   async getRecommendations(
     @Param('userId') userId: string,
     @CurrentUser() currentUser: User,
   ) {
     // CRITICAL: Verify user can only access their own recommendations
     if (currentUser.id !== userId && !currentUser.isAdmin) {
       throw new ForbiddenException('Cannot access other user recommendations');
     }
     // ...
   }
   ```

2. **XSS Prevention**
   - Sanitize ALL LLM-generated content before rendering
   - Use React's built-in escaping, but double-check `dangerouslySetInnerHTML`
   - Never render raw HTML from recommendations
   ```tsx
   // NEVER do this with LLM content:
   <div dangerouslySetInnerHTML={{ __html: recommendation.reason }} />

   // ALWAYS sanitize or use text content:
   <p>{sanitizeText(recommendation.reason)}</p>
   ```

3. **CSRF Protection**
   - All mutation endpoints must validate CSRF tokens
   - Use SameSite cookies

4. **Rate Limiting on Frontend**
   - Debounce recommendation refresh requests
   - Prevent spam clicking on ping/connect buttons
   ```tsx
   const { refresh, isRefreshing } = useRecommendations(eventId);

   // Debounced refresh
   const debouncedRefresh = useMemo(
     () => debounce(refresh, 2000, { leading: true, trailing: false }),
     [refresh]
   );
   ```

5. **Input Validation**
   - Validate all user inputs on BOTH client and server
   - Use Zod schemas that match backend Pydantic models
   ```typescript
   // shared-libs/common/src/schemas/feedback.ts
   export const connectionFeedbackSchema = z.object({
     connectionId: z.string().cuid(),
     rating: z.number().int().min(1).max(5),
     factors: z.array(z.string().max(50)).max(10),
     willFollowUp: z.boolean().optional(),
     comments: z.string().max(1000).optional(),
   });
   ```

### Performance Optimization

1. **React Query Caching**
   - Configure proper staleTime and cacheTime
   - Use query invalidation strategically
   ```typescript
   // hooks/use-recommendations.ts
   const query = useQuery({
     queryKey: ['recommendations', eventId, userId],
     queryFn: fetchRecommendations,
     staleTime: 1000 * 60 * 5,    // 5 minutes - don't refetch if fresh
     cacheTime: 1000 * 60 * 30,   // 30 minutes - keep in cache
     refetchOnWindowFocus: false,  // Don't spam API on tab switch
     retry: 2,                     // Retry failed requests twice
   });
   ```

2. **Component Optimization**
   - Memoize expensive components
   - Use virtualization for long lists
   - Lazy load recommendation cards
   ```tsx
   // Virtualized list for many recommendations
   import { useVirtualizer } from '@tanstack/react-virtual';

   const RecommendationsList = ({ recommendations }) => {
     const parentRef = useRef<HTMLDivElement>(null);

     const virtualizer = useVirtualizer({
       count: recommendations.length,
       getScrollElement: () => parentRef.current,
       estimateSize: () => 200, // Estimated card height
     });

     return (
       <div ref={parentRef} className="h-[600px] overflow-auto">
         <div style={{ height: virtualizer.getTotalSize() }}>
           {virtualizer.getVirtualItems().map((virtualItem) => (
             <RecommendationCard
               key={virtualItem.key}
               recommendation={recommendations[virtualItem.index]}
               style={{
                 position: 'absolute',
                 top: virtualItem.start,
                 height: virtualItem.size,
               }}
             />
           ))}
         </div>
       </div>
     );
   };
   ```

3. **API Response Optimization**
   - Only return fields needed by frontend
   - Paginate large result sets
   - Use GraphQL fragments for precise data fetching
   ```typescript
   // Return only display-necessary fields
   interface RecommendationResponse {
     userId: string;
     matchScore: number;
     reasons: string[];        // Max 3
     conversationStarters: string[];  // Max 2
     user: {
       id: string;
       name: string;
       role: string;
       company: string;
       avatarUrl?: string;
       // DON'T include: email, phone, full profile, etc.
     };
   }
   ```

4. **Bundle Optimization**
   - Lazy load recommendation features
   - Code split by route
   - Analyze bundle size regularly
   ```tsx
   // Lazy load heavy components
   const RecommendationsPanel = lazy(() =>
     import('@/components/features/networking/recommendations-panel')
   );

   // In parent component
   <Suspense fallback={<RecommendationsSkeleton />}>
     <RecommendationsPanel eventId={eventId} />
   </Suspense>
   ```

### Code Quality

1. **TypeScript Strict Mode**
   - Enable all strict checks in tsconfig
   - NO `any` types - use `unknown` and type guards
   - Export types for all public interfaces
   ```json
   // tsconfig.json
   {
     "compilerOptions": {
       "strict": true,
       "noImplicitAny": true,
       "strictNullChecks": true,
       "noUncheckedIndexedAccess": true
     }
   }
   ```

2. **Error Boundaries**
   - Wrap all feature components in error boundaries
   - Show graceful fallbacks, not white screens
   ```tsx
   <ErrorBoundary
     fallback={<NetworkingErrorFallback />}
     onError={(error) => captureException(error)}
   >
     <RecommendationsPanel eventId={eventId} />
   </ErrorBoundary>
   ```

3. **Testing Requirements**
   - Unit tests for hooks (React Testing Library)
   - Component tests for UI
   - E2E tests for critical flows (Playwright)
   - API contract tests
   ```typescript
   // __tests__/hooks/use-recommendations.test.ts
   describe('useRecommendations', () => {
     it('returns cached data while refetching', async () => {
       const { result, rerender } = renderHook(
         () => useRecommendations('event-123'),
         { wrapper: QueryClientProvider }
       );

       await waitFor(() => expect(result.current.isLoading).toBe(false));
       expect(result.current.recommendations).toHaveLength(10);
     });

     it('handles API errors gracefully', async () => {
       server.use(
         rest.get('/api/recommendations/*', (req, res, ctx) =>
           res(ctx.status(500))
         )
       );

       const { result } = renderHook(() => useRecommendations('event-123'));
       await waitFor(() => expect(result.current.error).toBeTruthy());
     });
   });
   ```

4. **Accessibility**
   - All interactive elements must be keyboard accessible
   - Proper ARIA labels
   - Color contrast compliance
   - Screen reader testing
   ```tsx
   <Button
     onClick={onPing}
     aria-label={`Send ping to ${user.name}`}
     disabled={isPinging}
   >
     {isPinging ? <Spinner aria-hidden /> : null}
     Ping
   </Button>
   ```

### File Structure

```
globalconnect/
├── src/
│   ├── app/
│   │   └── (main)/
│   │       └── events/
│   │           └── [eventId]/
│   │               └── networking/
│   │                   └── page.tsx
│   ├── components/
│   │   └── features/
│   │       ├── networking/
│   │       │   ├── recommendations-panel.tsx
│   │       │   ├── recommendation-card.tsx
│   │       │   └── recommendations-skeleton.tsx
│   │       └── feedback/
│   │           ├── connection-feedback-modal.tsx
│   │           └── feedback-campaign-banner.tsx
│   ├── hooks/
│   │   ├── use-recommendations.ts
│   │   ├── use-connection-feedback.ts
│   │   └── use-recommendation-actions.ts
│   └── lib/
│       ├── api/
│       │   └── recommendations.ts
│       └── schemas/
│           └── feedback.ts

api-gateway/
├── src/
│   ├── recommendations/
│   │   ├── recommendations.module.ts
│   │   ├── recommendations.controller.ts
│   │   ├── recommendations.service.ts
│   │   └── dto/
│   │       └── recommendation.dto.ts
│   ├── feedback/
│   │   ├── feedback.module.ts
│   │   ├── feedback.controller.ts
│   │   ├── feedback.service.ts
│   │   └── dto/
│   └── automation/
│       ├── automation.module.ts
│       └── triggers.service.ts
```

### Deliverables Checklist

Sprint 3:
- [ ] Recommendation service calling oracle-ai-service
- [ ] Caching layer for recommendations
- [ ] API endpoints: GET recommendations, POST refresh, POST viewed/pinged
- [ ] DTO validation with class-validator
- [ ] Integration tests with mocked oracle service

Sprint 4:
- [ ] RecommendationsPanel component
- [ ] RecommendationCard with expand/collapse
- [ ] Tabbed networking interface (Nearby + For You)
- [ ] useRecommendations hook with React Query
- [ ] Loading skeletons and error states
- [ ] Accessibility audit pass

Sprint 5:
- [ ] Event check-in trigger for recommendations
- [ ] Daily cron job for recommendation refresh
- [ ] Recommendation analytics tracking
- [ ] Performance monitoring setup

Sprint 10:
- [ ] ConnectionFeedback modal component
- [ ] Feedback campaign service (24-48h post-event)
- [ ] Email templates for feedback requests
- [ ] Feedback API endpoints
- [ ] A/B test variant tracking

### Commands to Run

```bash
# Frontend
cd globalconnect
pnpm install
pnpm dev

# Testing
pnpm test
pnpm test:e2e
pnpm lint
pnpm type-check

# API Gateway
cd api-gateway
pnpm install
pnpm start:dev
pnpm test
```

## START IMPLEMENTATION

Begin with Sprint 3, Phase 3 of the specification. Create the recommendation service first, then build the API endpoints, then move to frontend.
```

---

### AGENT PROMPT: Track C - Social Features

```markdown
# Track C: Social Features Implementation

You are implementing the real-time social features for GlobalConnect's networking system. Your track owns `real-time-service` WebSocket gateways and social-focused frontend components.

## Your Sprints
- Sprint 6: Facilitated Huddles
- Sprint 7: Post-Event Value & Retention

## Specification Reference
Read the full specification at: `AI_MATCHMAKING_SPEC.md`
Focus on: Phase 6, Phase 7

---

## CRITICAL REQUIREMENTS

### Security (NON-NEGOTIABLE)

1. **WebSocket Authentication**
   - EVERY WebSocket connection must be authenticated
   - Validate JWT on connection, not just on subscribe
   - Re-validate on reconnection
   ```typescript
   // real-time-service/src/common/guards/ws-auth.guard.ts
   @Injectable()
   export class WsAuthGuard implements CanActivate {
     canActivate(context: ExecutionContext): boolean {
       const client = context.switchToWs().getClient<Socket>();
       const token = client.handshake.auth?.token;

       if (!token) {
         throw new WsException('Missing authentication token');
       }

       try {
         const payload = this.jwtService.verify(token);
         client.data.userId = payload.sub;
         client.data.user = payload;
         return true;
       } catch (e) {
         throw new WsException('Invalid token');
       }
     }
   }
   ```

2. **Authorization Checks**
   - Users can only join rooms for events they're registered for
   - Users can only invite to huddles they're part of
   - Validate all user IDs in payloads
   ```typescript
   @SubscribeMessage('join_huddle')
   async handleJoinHuddle(
     @ConnectedSocket() client: Socket,
     @MessageBody() data: JoinHuddleDto,
   ) {
     const userId = client.data.userId;

     // Verify user is invited to this huddle
     const participant = await this.huddleService.getParticipant(
       data.huddleId,
       userId
     );

     if (!participant) {
       throw new WsException('Not invited to this huddle');
     }

     // Verify huddle is for an event user is registered for
     const huddle = await this.huddleService.getHuddle(data.huddleId);
     const isRegistered = await this.eventService.isUserRegistered(
       huddle.eventId,
       userId
     );

     if (!isRegistered) {
       throw new WsException('Not registered for this event');
     }

     await client.join(`huddle:${data.huddleId}`);
   }
   ```

3. **Rate Limiting WebSocket Events**
   - Prevent spam by limiting events per second
   - Implement backpressure for slow clients
   ```typescript
   // Throttle huddle responses
   @UseGuards(WsThrottlerGuard)
   @Throttle(5, 60) // 5 events per 60 seconds
   @SubscribeMessage('respond_to_huddle')
   async handleHuddleResponse(...) { }
   ```

4. **Data Validation**
   - Validate ALL WebSocket payloads with class-validator
   - Reject malformed messages immediately
   ```typescript
   // dto/respond-huddle.dto.ts
   export class RespondHuddleDto {
     @IsString()
     @IsNotEmpty()
     @MaxLength(50)
     huddleId: string;

     @IsEnum(['accept', 'decline'])
     response: 'accept' | 'decline';
   }

   // In gateway, validation pipe applies automatically
   @UsePipes(new ValidationPipe({ transform: true, whitelist: true }))
   @WebSocketGateway({ namespace: '/huddles' })
   export class HuddlesGateway { }
   ```

5. **Connection Privacy**
   - Users can only see connections they're part of
   - Hide email/phone from connection cards
   - Implement blocking functionality
   ```typescript
   async getConnectionsForUser(userId: string) {
     const connections = await this.prisma.connection.findMany({
       where: {
         OR: [
           { userId },
           { connectedUserId: userId },
         ],
         // Exclude blocked connections
         NOT: {
           blocked: true,
         },
       },
       include: {
         // Only include safe fields
         connectedUser: {
           select: {
             id: true,
             name: true,
             role: true,
             company: true,
             avatarUrl: true,
             // NO: email, phone, etc.
           },
         },
       },
     });
   }
   ```

### Performance Optimization

1. **Redis for Real-time State**
   - Store active huddle state in Redis, not PostgreSQL
   - Use Redis Pub/Sub for cross-instance events
   ```typescript
   // Store huddle participant counts in Redis for fast access
   async updateHuddleParticipantCount(huddleId: string) {
     const count = await this.prisma.huddleParticipant.count({
       where: { huddleId, status: 'ACCEPTED' },
     });

     await this.redis.hset(`huddle:${huddleId}`, 'participantCount', count);
     await this.redis.expire(`huddle:${huddleId}`, 86400); // 24h TTL
   }

   // Read from Redis first, DB as fallback
   async getHuddleQuickStats(huddleId: string) {
     const cached = await this.redis.hgetall(`huddle:${huddleId}`);
     if (cached?.participantCount) {
       return { participantCount: parseInt(cached.participantCount) };
     }

     // Fallback to DB
     return this.computeAndCacheStats(huddleId);
   }
   ```

2. **Efficient Broadcasting**
   - Use room-based broadcasting, not iterating sockets
   - Batch notifications when possible
   ```typescript
   // GOOD: Room broadcast
   this.server.to(`huddle:${huddleId}`).emit('participant_joined', payload);

   // BAD: Iterating all sockets
   for (const participant of participants) {
     this.server.to(`user:${participant.userId}`).emit(...);
   }
   ```

3. **Connection Cleanup**
   - Clean up stale connections on disconnect
   - Implement heartbeat for presence
   ```typescript
   @WebSocketGateway()
   export class BaseGateway implements OnGatewayDisconnect {
     async handleDisconnect(client: Socket) {
       const userId = client.data.userId;
       if (!userId) return;

       // Update user's online status
       await this.presenceService.setOffline(userId);

       // Leave all rooms
       const rooms = Array.from(client.rooms);
       for (const room of rooms) {
         if (room !== client.id) {
           await this.handleRoomLeave(userId, room);
         }
       }
     }
   }
   ```

4. **Database Query Optimization**
   - Use proper indexes for connection queries
   - Avoid N+1 queries in connection lists
   ```typescript
   // Use include to eager load, avoid N+1
   const connections = await this.prisma.connection.findMany({
     where: { userId },
     include: {
       connectedUser: true,
       originEvent: { select: { id: true, name: true } },
       activities: {
         take: 5,
         orderBy: { createdAt: 'desc' },
       },
     },
   });
   ```

### Code Quality

1. **Gateway Organization**
   - One gateway per feature domain
   - Shared base gateway for common functionality
   ```typescript
   // Base gateway with auth and error handling
   export abstract class BaseAuthenticatedGateway {
     @UseGuards(WsAuthGuard)
     abstract handleConnection(client: Socket): void;

     protected getUserId(client: Socket): string {
       return client.data.userId;
     }

     protected emitError(client: Socket, message: string) {
       client.emit('error', { message, timestamp: new Date() });
     }
   }

   // Feature gateway extends base
   @WebSocketGateway({ namespace: '/huddles' })
   export class HuddlesGateway extends BaseAuthenticatedGateway {
     // ...
   }
   ```

2. **Event Schema Documentation**
   - Document ALL WebSocket events
   - Use TypeScript interfaces for payloads
   ```typescript
   /**
    * WebSocket Events - Huddles Namespace
    *
    * Client -> Server:
    * - 'join_huddle' { huddleId: string }
    * - 'respond_to_huddle' { huddleId: string, response: 'accept'|'decline' }
    * - 'leave_huddle' { huddleId: string }
    *
    * Server -> Client:
    * - 'huddle_invitation' HuddleInvitationPayload
    * - 'participant_joined' ParticipantJoinedPayload
    * - 'huddle_confirmed' HuddleConfirmedPayload
    * - 'huddle_cancelled' { huddleId: string, reason: string }
    */
   ```

3. **Testing WebSockets**
   - Use socket.io-client for integration tests
   - Test connection lifecycle
   - Test authorization failures
   ```typescript
   describe('HuddlesGateway', () => {
     let clientSocket: Socket;

     beforeEach((done) => {
       clientSocket = io('http://localhost:3001/huddles', {
         auth: { token: validJwt },
       });
       clientSocket.on('connect', done);
     });

     afterEach(() => {
       clientSocket.disconnect();
     });

     it('rejects unauthenticated connections', (done) => {
       const unauthClient = io('http://localhost:3001/huddles');
       unauthClient.on('connect_error', (err) => {
         expect(err.message).toContain('authentication');
         done();
       });
     });

     it('broadcasts participant joined to room', (done) => {
       clientSocket.emit('respond_to_huddle', {
         huddleId: 'huddle-123',
         response: 'accept',
       });

       clientSocket.on('participant_joined', (data) => {
         expect(data.huddleId).toBe('huddle-123');
         done();
       });
     });
   });
   ```

### File Structure

```
real-time-service/
├── src/
│   ├── main.ts
│   ├── app.module.ts
│   ├── common/
│   │   ├── guards/
│   │   │   ├── ws-auth.guard.ts
│   │   │   └── ws-throttler.guard.ts
│   │   ├── filters/
│   │   │   └── ws-exception.filter.ts
│   │   ├── decorators/
│   │   │   └── ws-user.decorator.ts
│   │   └── base/
│   │       └── base-authenticated.gateway.ts
│   ├── huddles/
│   │   ├── huddles.module.ts
│   │   ├── huddles.gateway.ts
│   │   ├── huddles.service.ts
│   │   └── dto/
│   │       ├── join-huddle.dto.ts
│   │       ├── respond-huddle.dto.ts
│   │       └── huddle-invitation.dto.ts
│   ├── connections/
│   │   ├── connections.module.ts
│   │   ├── connections.gateway.ts
│   │   ├── connections.service.ts
│   │   └── dto/
│   └── retention/
│       ├── retention.module.ts
│       ├── follow-up.service.ts
│       └── digest.service.ts
├── test/
│   ├── huddles.gateway.spec.ts
│   ├── connections.gateway.spec.ts
│   └── test-utils/
│       └── socket-client.ts

globalconnect/
├── src/
│   ├── components/
│   │   └── features/
│   │       ├── huddles/
│   │       │   ├── huddle-invitation.tsx
│   │       │   ├── huddle-card.tsx
│   │       │   └── active-huddles-list.tsx
│   │       └── network/
│   │           ├── network-page.tsx
│   │           ├── connection-card.tsx
│   │           ├── connection-activity-feed.tsx
│   │           └── events-with-network.tsx
│   ├── hooks/
│   │   ├── use-huddles.ts
│   │   ├── use-connections.ts
│   │   └── use-follow-up-reminders.ts
│   └── lib/
│       └── sockets/
│           ├── huddles-socket.ts
│           └── connections-socket.ts
```

### Deliverables Checklist

Sprint 6:
- [ ] Huddle and HuddleParticipant database models
- [ ] HuddlesGateway with all WebSocket events
- [ ] Huddle invitation flow (invite -> accept/decline -> confirm)
- [ ] HuddleInvitation frontend component
- [ ] Problem statement capture in registration
- [ ] Huddle eligibility checker (min attendees)
- [ ] Integration tests for gateway

Sprint 7:
- [ ] Connection and ConnectionActivity models
- [ ] Connections service with strength calculation
- [ ] Follow-up generator calling oracle-ai-service
- [ ] Follow-up reminder UI component
- [ ] "Your Network" page
- [ ] Events with connections discovery
- [ ] Monthly digest email service
- [ ] Retention trigger automation (cron jobs)

### Commands to Run

```bash
# Real-time service
cd real-time-service
pnpm install
pnpm start:dev

# Testing
pnpm test
pnpm test:e2e

# WebSocket testing
pnpm test:ws
```

## START IMPLEMENTATION

Begin with Sprint 6, Phase 6 of the specification. Create the database models first, then the gateway, then the frontend components.
```

---

## Cross-Track Coordination Protocol

### Daily Sync Format

```markdown
## Daily Sync - [Date]

### Track A (Backend/AI)
- Completed: [list]
- Blocked on: [list]
- Need from other tracks: [list]

### Track B (Core Features)
- Completed: [list]
- Blocked on: [list]
- Need from other tracks: [list]

### Track C (Social Features)
- Completed: [list]
- Blocked on: [list]
- Need from other tracks: [list]

### Integration Issues
- [list any cross-track bugs or blockers]

### Schema Changes (REQUIRES ALL TRACK APPROVAL)
- [list any proposed schema changes]
```

### API Contract Template

```typescript
/**
 * API Contract: [Endpoint Name]
 * Owner: Track [A/B/C]
 * Consumers: Track [X, Y]
 *
 * Endpoint: [METHOD] /api/[path]
 *
 * Request:
 * [TypeScript interface]
 *
 * Response:
 * [TypeScript interface]
 *
 * Error Codes:
 * - 400: [reason]
 * - 401: [reason]
 * - 403: [reason]
 * - 404: [reason]
 * - 500: [reason]
 *
 * Rate Limits:
 * - [X] requests per [timeframe]
 *
 * Notes:
 * - [any special considerations]
 */
```

### Schema Change Request Template

```markdown
## Schema Change Request

**Requester:** Track [X]
**Date:** [date]
**Priority:** [High/Medium/Low]

### Proposed Change
```prisma
// Current
model Example {
  // ...
}

// Proposed
model Example {
  // ... with changes highlighted
}
```

### Reason for Change
[Explain why this is needed]

### Impact Analysis
- Track A impact: [none/minor/major]
- Track B impact: [none/minor/major]
- Track C impact: [none/minor/major]

### Migration Plan
[How to migrate existing data]

### Approval
- [ ] Track A approved
- [ ] Track B approved
- [ ] Track C approved
```
