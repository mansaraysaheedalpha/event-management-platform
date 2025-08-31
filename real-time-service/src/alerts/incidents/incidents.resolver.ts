import { Resolver, Query, Args } from '@nestjs/graphql';
import { IncidentTypeObject } from '../../graphql/types';
import { PrismaService } from '../../prisma.service';
import { Incident } from '@prisma/client';

@Resolver(() => IncidentTypeObject)
export class IncidentsResolver {
  constructor(private prisma: PrismaService) {}

  @Query(() => IncidentTypeObject, { nullable: true })
  async incident(@Args('id') id: string): Promise<Incident | null> {
    return this.prisma.incident.findUnique({
      where: { id },
    });
  }
}
