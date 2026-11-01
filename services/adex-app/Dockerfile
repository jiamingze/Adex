FROM maven:3.9-eclipse-temurin-26 AS build
WORKDIR /src
COPY pom.xml ./
COPY packages/java-kernel packages/java-kernel
COPY services/adex-app services/adex-app
COPY services/adex-automation services/adex-automation
RUN --mount=type=cache,id=adex-maven,target=/root/.m2,sharing=locked mvn -B -pl services/adex-app -am package -DskipTests
FROM eclipse-temurin:21-jre-alpine
RUN addgroup -g 10001 adex && adduser -D -u 10001 -G adex adex && mkdir -p /var/adex/files && chown adex:adex /var/adex/files
WORKDIR /opt/adex
COPY --from=build /src/services/adex-app/target/adex-app-0.1.0.jar app.jar
USER 10001:10001
ENV BIND_ADDRESS=0.0.0.0 ADEX_SERVICE=app
ENTRYPOINT ["java","-XX:MaxRAMPercentage=60","-jar","app.jar"]
