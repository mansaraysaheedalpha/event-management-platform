// src/app/(platform)/events/page.tsx
"use client";

import { useState } from "react";
import { useQuery } from "@apollo/client";
import Link from "next/link";
import { useDebounce } from "@/hooks/use-debounce";
import {
  PlusCircle,
  AlertTriangle,
  LayoutGrid,
  List,
  Users,
  Calendar,
  BarChart,
  Search,
} from "lucide-react";
import {
  GET_EVENTS_QUERY,
  GET_EVENT_STATS_QUERY,
} from "@/graphql/events.graphql";
import { Button } from "@/components/ui/button";
import { Loader } from "@/components/ui/loader";
import { EventCard } from "@/components/features/events/EventCard";
import { EventRow } from "@/components/features/events/EventRow";
import { EventEmptyState } from "@/components/features/events/EventEmptyState";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const StatCard = ({ title, value, icon: Icon }) => (
  <Card>
    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
      <CardTitle className="text-sm font-medium">{title}</CardTitle>
      <Icon className="h-4 w-4 text-muted-foreground" />
    </CardHeader>
    <CardContent>
      <div className="text-2xl font-bold">{value}</div>
    </CardContent>
  </Card>
);

export default function EventsPage() {
  const [searchTerm, setSearchTerm] = useState("");
  const debouncedSearchTerm = useDebounce(searchTerm, 500);
  const [statusFilter, setStatusFilter] = useState("all");
  const [sortBy, setSortBy] = useState("startDate:desc");
  const [viewMode, setViewMode] = useState("grid"); // 'grid' or 'list'
  const [page, setPage] = useState(1);
  const eventsPerPage = 6;

  const { data, loading, error } = useQuery(GET_EVENTS_QUERY, {
    variables: {
      search: debouncedSearchTerm,
      status: statusFilter === "all" ? null : statusFilter,
      sortBy: sortBy.split(":")[0],
      sortDirection: sortBy.split(":")[1],
      limit: eventsPerPage,
      offset: (page - 1) * eventsPerPage,
    },
  });
  const { data: statsData } = useQuery(GET_EVENT_STATS_QUERY);

  const events = data?.eventsByOrganization?.events || [];
  const stats = statsData?.eventStats || {
    totalEvents: 0,
    upcomingEvents: 0,
    upcomingRegistrations: 0,
  };

  const filteredEvents = events;
  const totalEvents = data?.eventsByOrganization?.totalCount || 0;
  const totalPages = Math.ceil(totalEvents / eventsPerPage);

  const renderContent = () => {
    if (loading) {
      return (
        <div className="flex justify-center items-center h-64">
          <Loader className="h-8 w-8" />
        </div>
      );
    }

    if (error) {
      return (
        <div className="text-center text-red-500 bg-red-50 p-6 rounded-md">
          <AlertTriangle className="mx-auto h-8 w-8 mb-2" />
          <p className="font-semibold">Error loading events</p>
          <p className="text-sm">{error.message}</p>
        </div>
      );
    }

    if (filteredEvents.length === 0) {
      return <EventEmptyState />;
    }

    if (viewMode === "grid") {
      return (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredEvents.map((event) => (
            <EventCard key={event.id} event={event} />
          ))}
        </div>
      );
    }
    if (viewMode === "list") {
      return (
        <div className="border rounded-lg overflow-hidden">
          <div className="flex items-center p-4 bg-muted/50 font-semibold text-sm border-b">
            <div className="flex-1">Event</div>
            <div className="w-40 text-center">Status</div>
            <div className="w-40 text-center">Visibility</div>
            <div className="w-40 text-center">Registrations</div>
            <div className="w-20 text-right">Actions</div>
          </div>
          <div>
            {filteredEvents.map((event) => (
              <EventRow key={event.id} event={event} />
            ))}
          </div>
        </div>
      );
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold">Events Dashboard</h1>
          <p className="text-muted-foreground">
            Your central hub for managing all events.
          </p>
        </div>
        <Button asChild>
          <Link href="/events/new">
            <PlusCircle className="mr-2 h-4 w-4" />
            Create Event
          </Link>
        </Button>
      </div>

      {/* Stats Section */}
      <div className="grid gap-4 md:grid-cols-3">
        <StatCard
          title="Total Events"
          value={stats.totalEvents}
          icon={BarChart}
        />
        <StatCard
          title="Upcoming Events"
          value={stats.upcomingEvents}
          icon={Calendar}
        />
        <StatCard
          title="Upcoming Registrations"
          value={stats.upcomingRegistrations}
          icon={Users}
        />
      </div>

      {/* Toolbar */}
      <div className="flex flex-col md:flex-row gap-4 justify-between items-center">
        <div className="relative w-full md:max-w-xs">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search events..."
            className="pl-8"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>
        <div className="flex gap-4">
          <Select value={statusFilter} onValueChange={setStatusFilter}>
            <SelectTrigger className="w-full md:w-[180px]">
              <SelectValue placeholder="Filter by status" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Statuses</SelectItem>
              <SelectItem value="published">Published</SelectItem>
              <SelectItem value="draft">Draft</SelectItem>
            </SelectContent>
          </Select>
          <Select value={sortBy} onValueChange={setSortBy}>
            <SelectTrigger className="w-full md:w-[180px]">
              <SelectValue placeholder="Sort by" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="startDate:desc">
                Start Date (Newest)
              </SelectItem>
              <SelectItem value="startDate:asc">Start Date (Oldest)</SelectItem>
              <SelectItem value="name:asc">Name (A-Z)</SelectItem>
              <SelectItem value="name:desc">Name (Z-A)</SelectItem>
            </SelectContent>
          </Select>
          <div className="flex items-center gap-2">
            <Button
              variant={viewMode === "grid" ? "default" : "outline"}
              size="icon"
              onClick={() => setViewMode("grid")}
            >
              <LayoutGrid className="h-4 w-4" />
            </Button>
            <Button
              variant={viewMode === "list" ? "default" : "outline"}
              size="icon"
              onClick={() => setViewMode("list")}
            >
              <List className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </div>

      {renderContent()}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex justify-center items-center gap-4">
          <Button
            variant="outline"
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
          >
            Previous
          </Button>
          <span className="text-sm font-medium">
            Page {page} of {totalPages}
          </span>
          <Button
            variant="outline"
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
          >
            Next
          </Button>
        </div>
      )}
    </div>
  );
}
