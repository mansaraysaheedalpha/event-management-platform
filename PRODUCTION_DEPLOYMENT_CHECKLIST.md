# Production Deployment Checklist

## Platform Recommendation: AWS (Amazon Web Services)

### Why AWS?
- Mature managed services for PostgreSQL (RDS), Kafka (MSK), Redis (ElastiCache)
- Excellent container orchestration (ECS Fargate or EKS)
- S3 for object storage (MinIO replacement)
- Application Load Balancer with WebSocket support
- Strong monitoring, logging, and security capabilities
- Cost-effective at scale

---

## PHASE 1: PRE-DEPLOYMENT PREPARATION

### 1.1 Code & Configuration Audit
- [ ] Review all hardcoded values and move to environment variables
- [ ] Ensure all services have proper health check endpoints (`/health`)
- [ ] Review and update all `.env.example` files with production-safe defaults
- [ ] Remove all test/development credentials from codebase
- [ ] Audit CORS configurations for production domains
- [ ] Review rate limiting configurations
- [ ] Check all API authentication/authorization flows

### 1.2 Database Preparation
- [ ] Review all Alembic migrations for event-lifecycle-service
- [ ] Review all Prisma migrations for real-time-service
- [ ] Review all database migrations for user-and-org-service
- [ ] Review all database migrations for oracle-ai-service
- [ ] Test migration rollback procedures
- [ ] Document database schemas
- [ ] Plan database backup strategy
- [ ] Review database indexes for performance
- [ ] Set up database connection pooling configurations

### 1.3 Security Hardening
- [ ] Audit all JWT secret keys (generate production secrets)
- [ ] Review password hashing configurations (bcrypt rounds)
- [ ] Enable HTTPS/TLS for all services
- [ ] Review API rate limiting (slowapi, nestjs/throttler)
- [ ] Audit file upload size limits and validation
- [ ] Review SQL injection prevention (parameterized queries)
- [ ] Check XSS prevention measures
- [ ] Review CSRF protection for relevant endpoints
- [ ] Audit Stripe webhook signature verification
- [ ] Set up secrets management (AWS Secrets Manager)

### 1.4 Monitoring & Logging Setup
- [ ] Choose logging strategy (CloudWatch, ELK, Datadog)
- [ ] Add structured logging to all services
- [ ] Set up error tracking (Sentry, Rollbar)
- [ ] Plan application metrics (Prometheus/CloudWatch)
- [ ] Set up uptime monitoring (UptimeRobot, Pingdom)
- [ ] Create alert rules for critical errors
- [ ] Set up log retention policies

### 1.5 Testing
- [ ] Run all unit tests (`pytest` for Python, `jest` for Node.js)
- [ ] Run integration tests
- [ ] Load test critical endpoints
- [ ] Test WebSocket connections under load
- [ ] Test Kafka message processing under load
- [ ] Test database failover scenarios
- [ ] Test backup and restore procedures

---

## PHASE 2: AWS INFRASTRUCTURE SETUP

### 2.1 AWS Account Setup
- [ ] Create AWS account (or use existing)
- [ ] Set up billing alerts
- [ ] Enable MFA for root account
- [ ] Create IAM admin user (don't use root)
- [ ] Set up AWS Organizations (if multi-environment)
- [ ] Choose primary AWS region (consider latency to users)

### 2.2 Networking (VPC)
- [ ] Create VPC for production environment
- [ ] Create public subnets (for load balancers) in 2+ AZs
- [ ] Create private subnets (for services) in 2+ AZs
- [ ] Create database subnets in 2+ AZs
- [ ] Set up Internet Gateway
- [ ] Set up NAT Gateway (for private subnet internet access)
- [ ] Configure route tables
- [ ] Create security groups for each service tier

### 2.3 Database Setup (RDS PostgreSQL)
- [ ] Create RDS PostgreSQL instance for event-lifecycle-service (Multi-AZ)
- [ ] Create RDS PostgreSQL instance for user-org-service (Multi-AZ)
- [ ] Create RDS PostgreSQL instance for real-time-service (Multi-AZ)
- [ ] Create RDS PostgreSQL instance for oracle-ai-service (Multi-AZ)
- [ ] Configure automated backups (30-day retention)
- [ ] Enable point-in-time recovery
- [ ] Set up parameter groups for optimization
- [ ] Configure security groups (only allow service access)
- [ ] Document connection strings
- [ ] Test connections from local machine via bastion/VPN

### 2.4 Caching (ElastiCache Redis)
- [ ] Create ElastiCache Redis cluster (Multi-AZ)
- [ ] Choose appropriate instance type (cache.t3.medium minimum)
- [ ] Enable automatic failover
- [ ] Configure security group
- [ ] Test connection from services

### 2.5 Message Queue (Amazon MSK - Kafka)
- [ ] Create Amazon MSK cluster (3 brokers minimum)
- [ ] Choose appropriate broker instance type (kafka.t3.small minimum)
- [ ] Configure topics (email-events, oracle-events, etc.)
- [ ] Set up appropriate retention policies
- [ ] Configure security group
- [ ] Document bootstrap servers endpoint
- [ ] Test connectivity from services

### 2.6 Object Storage (S3)
- [ ] Create S3 bucket for file uploads
- [ ] Configure bucket policies and CORS
- [ ] Enable versioning
- [ ] Set up lifecycle policies (archive/delete old files)
- [ ] Enable server-side encryption
- [ ] Set up CloudFront CDN (optional, for performance)
- [ ] Create IAM role for service access
- [ ] Update application configs (replace MinIO with S3)

### 2.7 Container Registry (ECR)
- [ ] Create ECR repositories for each service:
  - [ ] apollo-gateway
  - [ ] user-and-org-service
  - [ ] event-lifecycle-service
  - [ ] real-time-service
  - [ ] oracle-ai-service
- [ ] Set up lifecycle policies (keep last 10 images)

---

## PHASE 3: APPLICATION DEPLOYMENT

### 3.1 Choose Container Orchestration
**Option A: ECS Fargate (Recommended for simplicity)**
- Serverless containers, no server management
- Pay only for running containers
- Easier to set up than Kubernetes

**Option B: EKS (Kubernetes)**
- More control and flexibility
- Better for complex deployments
- Higher learning curve and operational overhead

### 3.2 ECS Fargate Setup (Recommended)
- [ ] Create ECS cluster
- [ ] Create task definitions for each service:
  - [ ] apollo-gateway (1 vCPU, 2GB RAM)
  - [ ] user-and-org-service (1 vCPU, 2GB RAM)
  - [ ] event-lifecycle-service (2 vCPU, 4GB RAM)
  - [ ] real-time-service (1 vCPU, 2GB RAM)
  - [ ] oracle-ai-service (2 vCPU, 4GB RAM)
  - [ ] event-celery-worker (1 vCPU, 2GB RAM)
  - [ ] email-consumer (0.5 vCPU, 1GB RAM)
  - [ ] oracle-consumer (0.5 vCPU, 1GB RAM)
- [ ] Configure environment variables for each task
- [ ] Set up CloudWatch log groups for each service
- [ ] Create ECS services for each task definition
- [ ] Configure auto-scaling policies (CPU/memory based)

### 3.3 Load Balancer Setup
- [ ] Create Application Load Balancer (ALB)
- [ ] Configure target groups for each service:
  - [ ] apollo-gateway (port 4000)
  - [ ] user-and-org-service (port 3001)
  - [ ] event-lifecycle-service (port 8000)
  - [ ] real-time-service (port 3002) - Enable WebSocket support
  - [ ] oracle-ai-service (port 8001)
- [ ] Configure health checks for each target group
- [ ] Set up SSL/TLS certificate (ACM)
- [ ] Configure HTTPS listener (port 443)
- [ ] Redirect HTTP to HTTPS
- [ ] Configure routing rules

### 3.4 Domain & DNS Setup
- [ ] Purchase/configure domain name
- [ ] Create Route 53 hosted zone
- [ ] Create DNS records:
  - [ ] api.yourdomain.com → ALB (Apollo Gateway)
  - [ ] ws.yourdomain.com → ALB (Real-time Service)
  - [ ] Or use path-based routing on single domain
- [ ] Request SSL certificate in ACM
- [ ] Validate domain ownership
- [ ] Attach certificate to ALB

### 3.5 Build & Push Docker Images
```bash
# Login to ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <account-id>.dkr.ecr.us-east-1.amazonaws.com

# Build and push each service
docker build -t apollo-gateway:latest ./apollo-gateway
docker tag apollo-gateway:latest <account-id>.dkr.ecr.us-east-1.amazonaws.com/apollo-gateway:latest
docker push <account-id>.dkr.ecr.us-east-1.amazonaws.com/apollo-gateway:latest

# Repeat for all services...
```

- [ ] Build apollo-gateway image
- [ ] Build user-and-org-service image
- [ ] Build event-lifecycle-service image
- [ ] Build real-time-service image
- [ ] Build oracle-ai-service image
- [ ] Tag all images with version numbers
- [ ] Push all images to ECR

### 3.6 Run Database Migrations
- [ ] Create bastion host or use AWS Systems Manager Session Manager
- [ ] Run Alembic migrations for event-lifecycle-service:
  ```bash
  alembic upgrade head
  ```
- [ ] Run Prisma migrations for real-time-service:
  ```bash
  npx prisma migrate deploy
  ```
- [ ] Run migrations for user-and-org-service
- [ ] Run migrations for oracle-ai-service
- [ ] Verify all tables are created correctly

### 3.7 Deploy Services
- [ ] Deploy apollo-gateway ECS service
- [ ] Deploy user-and-org-service ECS service
- [ ] Deploy event-lifecycle-service ECS service
- [ ] Deploy real-time-service ECS service
- [ ] Deploy oracle-ai-service ECS service
- [ ] Deploy event-celery-worker ECS service
- [ ] Deploy email-consumer ECS service
- [ ] Deploy oracle-consumer ECS service
- [ ] Verify all services are healthy in ECS console
- [ ] Check CloudWatch logs for errors

---

## PHASE 4: POST-DEPLOYMENT VALIDATION

### 4.1 Smoke Tests
- [ ] Test Apollo Gateway GraphQL endpoint
- [ ] Test user registration/login flow
- [ ] Test event creation
- [ ] Test WebSocket connection (real-time-service)
- [ ] Test file upload to S3
- [ ] Test Kafka message flow (check consumers)
- [ ] Test email sending (check email-consumer logs)
- [ ] Test Stripe payment flow
- [ ] Test AI oracle service
- [ ] Test waitlist functionality
- [ ] Test ads functionality
- [ ] Test A/B testing endpoints
- [ ] Test analytics endpoints

### 4.2 Performance Validation
- [ ] Check API response times (< 500ms for most endpoints)
- [ ] Monitor database query performance
- [ ] Check Redis cache hit rates
- [ ] Monitor Kafka consumer lag
- [ ] Test WebSocket connection stability
- [ ] Run load tests on critical endpoints

### 4.3 Monitoring Setup
- [ ] Verify CloudWatch dashboards are populating
- [ ] Set up alarms for:
  - [ ] High error rates (5xx responses)
  - [ ] High response times
  - [ ] Database connection pool exhaustion
  - [ ] Kafka consumer lag
  - [ ] Redis connection failures
  - [ ] ECS task failures
- [ ] Set up SNS topics for alerts
- [ ] Configure email/SMS notifications

---

## PHASE 5: OPERATIONAL SETUP

### 5.1 CI/CD Pipeline
- [ ] Set up GitHub Actions / GitLab CI / AWS CodePipeline
- [ ] Configure automated testing in pipeline
- [ ] Set up automatic Docker image builds
- [ ] Configure automatic deployment to staging
- [ ] Set up manual approval for production deployments
- [ ] Document rollback procedures

### 5.2 Backup & Disaster Recovery
- [ ] Verify RDS automated backups are running
- [ ] Test database restore procedure
- [ ] Set up S3 bucket versioning
- [ ] Create disaster recovery runbook
- [ ] Test complete system restore from backups

### 5.3 Cost Optimization
- [ ] Set up AWS Cost Explorer
- [ ] Review resource utilization
- [ ] Right-size ECS tasks (reduce unused CPU/memory)
- [ ] Consider Reserved Instances for RDS (1-year commitment)
- [ ] Set up S3 lifecycle policies to archive old data
- [ ] Review and optimize Kafka retention policies

### 5.4 Security Hardening
- [ ] Enable AWS WAF on ALB (DDoS protection)
- [ ] Enable GuardDuty (threat detection)
- [ ] Set up AWS Config (compliance monitoring)
- [ ] Enable CloudTrail (API audit logging)
- [ ] Review IAM roles and permissions (least privilege)
- [ ] Enable VPC Flow Logs
- [ ] Set up automated security scanning (Snyk, Dependabot)

### 5.5 Documentation
- [ ] Document deployment architecture (with diagrams)
- [ ] Create runbook for common operations
- [ ] Document incident response procedures
- [ ] Create API documentation (Swagger/GraphQL schema)
- [ ] Document environment variables for each service
- [ ] Create onboarding guide for new developers

---

## PHASE 6: PRODUCTION LAUNCH

### 6.1 Pre-Launch Checklist
- [ ] All critical features tested in production environment
- [ ] Load testing completed successfully
- [ ] All monitoring and alerts configured
- [ ] Backup and restore tested
- [ ] Security audit completed
- [ ] Team trained on operations and incident response
- [ ] Rollback plan documented and tested

### 6.2 Launch
- [ ] Announce maintenance window (if migrating from existing system)
- [ ] Update DNS records to point to production
- [ ] Monitor all services closely for first 24 hours
- [ ] Check error rates, response times, and logs
- [ ] Verify all background jobs are running

### 6.3 Post-Launch
- [ ] Monitor user feedback
- [ ] Address any immediate issues
- [ ] Review performance metrics
- [ ] Optimize based on real traffic patterns
- [ ] Schedule regular maintenance windows
- [ ] Plan for future scaling needs

---

## Estimated Costs (AWS - Starting Small)

**Monthly Estimates:**
- RDS PostgreSQL (4 instances, db.t3.medium): ~$280
- ElastiCache Redis (cache.t3.medium): ~$70
- Amazon MSK (3 brokers, kafka.t3.small): ~$300
- S3 Storage (100GB): ~$3
- ECS Fargate (8 services, moderate traffic): ~$200-400
- ALB: ~$25
- Data Transfer: ~$50-100
- CloudWatch/Monitoring: ~$50

**Total: ~$1,000-1,500/month** (will scale with traffic)

**Cost Optimization Tips:**
- Start with smaller instance types and scale up
- Use Savings Plans for 20-30% discount
- Enable auto-scaling to reduce costs during low traffic
- Consider Aurora Serverless for databases (pay per use)

---

## Alternative: DigitalOcean (Simpler, Lower Cost)

If AWS feels overwhelming, DigitalOcean App Platform is simpler:

**Pros:**
- Much simpler setup (no VPC, security groups, etc.)
- Lower costs (~$500-800/month to start)
- Good documentation and support
- Managed databases included

**Cons:**
- No managed Kafka (need to run yourself or use external service like Confluent Cloud)
- Less scalable long-term
- Fewer advanced features

**DigitalOcean Setup:**
1. Create managed PostgreSQL databases (4 instances)
2. Create managed Redis cluster
3. Set up App Platform apps for each service
4. Use Spaces (S3-compatible) for object storage
5. Use external Kafka service (Confluent Cloud) or self-host

---

## Quick Start: Deploy to AWS in Steps

**Week 1: Infrastructure**
- Set up AWS account, VPC, and networking
- Create RDS databases, ElastiCache, MSK
- Set up S3 bucket and ECR repositories

**Week 2: Application**
- Build and push Docker images
- Create ECS task definitions and services
- Set up ALB and SSL certificates
- Run database migrations

**Week 3: Testing & Monitoring**
- Deploy all services to staging
- Run comprehensive tests
- Set up monitoring and alerts
- Load test critical paths

**Week 4: Production Launch**
- Deploy to production
- Configure DNS
- Monitor closely
- Iterate based on feedback

---

## Need Help?

Common issues and solutions:

**Services can't connect to databases:**
- Check security group rules
- Verify connection strings
- Check VPC subnet configurations

**High costs:**
- Right-size your resources
- Enable auto-scaling
- Review CloudWatch metrics for unused capacity

**Slow performance:**
- Check database query performance
- Increase Redis cache usage
- Add database indexes
- Scale up ECS task resources

**Kafka consumer lag:**
- Scale up consumer instances
- Optimize message processing logic
- Increase Kafka partition count

---

## Conclusion

This checklist will guide you through deploying your event management platform to production on AWS. The process takes 3-4 weeks for a complete, production-ready deployment. Start with a staging environment first to validate everything before going live.

Good luck with your deployment! 🚀
