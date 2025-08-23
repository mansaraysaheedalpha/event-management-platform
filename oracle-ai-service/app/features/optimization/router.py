# app/features/optimization/router.py
from fastapi import APIRouter
from .schemas import *
from . import service

router = APIRouter()


@router.post(
    "/optimization/schedule",
    response_model=ScheduleOptimizationResponse,
    tags=["Dynamic Optimization"],
)
def get_schedule_optimization(request: ScheduleOptimizationRequest):
    """
    Suggests schedule optimizations to reduce crowding and resolve conflicts.
    """
    return service.optimize_schedule(request)


@router.post(
    "/optimization/capacity-management",
    response_model=CapacityManagementResponse,
    tags=["Dynamic Optimization"],
)
def get_capacity_management(request: CapacityManagementRequest):
    """Predicts and manages session capacity."""
    return service.manage_capacity(request)


@router.post(
    "/optimization/resource-allocation",
    response_model=ResourceAllocationResponse,
    tags=["Dynamic Optimization"],
)
def get_resource_optimization(request: ResourceAllocationRequest):
    """Optimizes staff deployment and resource allocation."""
    return service.optimize_resources(request)
