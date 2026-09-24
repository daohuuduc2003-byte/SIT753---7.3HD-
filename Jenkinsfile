pipeline {
    agent any

    options {
        buildDiscarder(logRotator(numToKeepStr: '15', artifactNumToKeepStr: '3'))
        timeout(time: 30, unit: 'MINUTES')
        disableConcurrentBuilds()
    }

    triggers {
        // Check GitHub for new commits every 5 minutes
        pollSCM('H/5 * * * *')
    }

    environment {
        PATH         = "/opt/homebrew/bin:/usr/local/bin:/Applications/Docker.app/Contents/Resources/bin:${env.PATH}"
        IMAGE_NAME   = 'rivertrail'
        IMAGE_TAG    = "1.0.${env.BUILD_NUMBER}"
        STAGING_PORT = '8081'
        PROD_PORT    = '8082'
        PROD_COMPOSE = 'deploy/docker-compose.prod.yml'
        GITHUB_REPO  = 'daohuuduc2003-byte/SIT753---7.3HD-'
    }

    stages {

        stage('Build') {
            steps {
                sh '''
                    echo "== Building ${IMAGE_NAME}:${IMAGE_TAG} from commit ${GIT_COMMIT} =="
                    docker build \
                      --label "org.opencontainers.image.version=${IMAGE_TAG}" \
                      --label "org.opencontainers.image.revision=${GIT_COMMIT}" \
                      -t ${IMAGE_NAME}:${IMAGE_TAG} \
                      -t ${IMAGE_NAME}:latest .
                    docker image inspect ${IMAGE_NAME}:${IMAGE_TAG} --format 'Built {{.RepoTags}} size={{.Size}} bytes'
                    docker save ${IMAGE_NAME}:${IMAGE_TAG} | gzip > rivertrail-${IMAGE_TAG}.tar.gz
                '''
            }
            post {
                success {
                    archiveArtifacts artifacts: 'rivertrail-*.tar.gz', fingerprint: true
                }
            }
        }

        stage('Test') {
            steps {
                sh '''
                    python3 -m venv venv
                    . venv/bin/activate
                    pip install -q --upgrade pip
                    pip install -q -r requirements-dev.txt
                    python -m pytest -v \
                      --junitxml=test-results.xml \
                      --cov=server --cov-report=xml --cov-report=term \
                      --cov-fail-under=70
                '''
            }
            post {
                always {
                    junit 'test-results.xml'
                    archiveArtifacts artifacts: 'coverage.xml', allowEmptyArchive: true
                }
            }
        }

        stage('Code Quality') {
            steps {
                withCredentials([string(credentialsId: 'sonarcloud-token', variable: 'SONAR_TOKEN')]) {
                    sh 'sonar-scanner -Dsonar.token=$SONAR_TOKEN -Dsonar.projectVersion=$IMAGE_TAG'
                }
            }
        }

        stage('Security') {
            steps {
                sh '''
                    . venv/bin/activate
                    pip install -q bandit pip-audit
                    mkdir -p reports

                    echo "== Bandit: static analysis of server.py =="
                    bandit -r server.py -f json -o reports/bandit.json || true
                    bandit -r server.py -f txt || true
                    echo "Gate: fail only on HIGH severity code issues"
                    bandit -r server.py -lll -q

                    echo "== pip-audit: known CVEs in Python dependencies =="
                    pip-audit -r requirements.txt -f json -o reports/pip-audit.json || true
                    pip-audit -r requirements.txt

                    echo "== Trivy: vulnerabilities in the container image =="
                    trivy image --scanners vuln --severity HIGH,CRITICAL \
                      --format table --output reports/trivy.txt ${IMAGE_NAME}:${IMAGE_TAG}
                    cat reports/trivy.txt
                    echo "Gate: fail on CRITICAL issues that have a fix available"
                    trivy image --scanners vuln --severity CRITICAL --ignore-unfixed \
                      --exit-code 1 ${IMAGE_NAME}:${IMAGE_TAG}
                '''
            }
            post {
                always {
                    archiveArtifacts artifacts: 'reports/*', allowEmptyArchive: true
                }
            }
        }

        stage('Deploy') {
            steps {
                sh '''
                    echo "== Deploying ${IMAGE_NAME}:${IMAGE_TAG} to staging on port ${STAGING_PORT} =="
                    docker rm -f rivertrail-staging 2>/dev/null || true
                    docker run -d --name rivertrail-staging \
                      -p ${STAGING_PORT}:3000 \
                      -v rivertrail-staging-data:/app/data \
                      -e APP_ENV=staging \
                      ${IMAGE_NAME}:${IMAGE_TAG}

                    echo "Waiting for staging to become healthy..."
                    for i in $(seq 1 15); do
                      curl -fs http://localhost:${STAGING_PORT}/health > /dev/null && break
                      sleep 2
                    done

                    echo "== Smoke tests against staging =="
                    . venv/bin/activate
                    SMOKE_BASE_URL=http://localhost:${STAGING_PORT} \
                      python -m pytest smoke -v --junitxml=smoke-staging.xml --junit-prefix=staging
                '''
            }
            post {
                always {
                    junit allowEmptyResults: true, testResults: 'smoke-staging.xml'
                }
            }
        }

        stage('Release') {
            steps {
                withCredentials([usernamePassword(credentialsId: 'github-pat',
                                                  usernameVariable: 'GH_USER',
                                                  passwordVariable: 'GH_TOKEN')]) {
                    sh '''
                        PREV_IMAGE=$(docker inspect -f '{{.Config.Image}}' rivertrail-prod 2>/dev/null || true)
                        echo "== Promoting ${IMAGE_NAME}:${IMAGE_TAG} to production on port ${PROD_PORT} =="
                        echo "Image currently in production: ${PREV_IMAGE:-none}"

                        rollback() {
                          echo "!! Production checks failed for ${IMAGE_NAME}:${IMAGE_TAG}"
                          if [ -n "$PREV_IMAGE" ] && [ "$PREV_IMAGE" != "${IMAGE_NAME}:${IMAGE_TAG}" ]; then
                            echo "Rolling production back to $PREV_IMAGE"
                            APP_IMAGE="$PREV_IMAGE" docker compose -f ${PROD_COMPOSE} up -d --no-deps app
                          else
                            echo "No earlier production image to roll back to"
                          fi
                          exit 1
                        }

                        APP_IMAGE=${IMAGE_NAME}:${IMAGE_TAG} docker compose -f ${PROD_COMPOSE} up -d --no-deps app

                        for i in $(seq 1 20); do
                          curl -fs http://localhost:${PROD_PORT}/health > /dev/null && break
                          sleep 2
                        done
                        curl -fs http://localhost:${PROD_PORT}/health > /dev/null || rollback

                        echo "== Read only smoke tests against production =="
                        . venv/bin/activate
                        SMOKE_BASE_URL=http://localhost:${PROD_PORT} SMOKE_READ_ONLY=1 \
                          python -m pytest smoke -v --junitxml=smoke-prod.xml --junit-prefix=production || rollback

                        docker tag ${IMAGE_NAME}:${IMAGE_TAG} ${IMAGE_NAME}:prod
                        echo "Production now runs ${IMAGE_NAME}:${IMAGE_TAG}"

                        echo "== Recording release v${IMAGE_TAG} on GitHub =="
                        python - > release.json <<'PY'
import json, os
tag = "v" + os.environ["IMAGE_TAG"]
print(json.dumps({
    "tag_name": tag,
    "target_commitish": os.environ["GIT_COMMIT"],
    "name": "River Trail " + tag,
    "body": "Automated release from Jenkins build " + os.environ["BUILD_NUMBER"]
            + ". Docker image " + os.environ["IMAGE_NAME"] + ":" + os.environ["IMAGE_TAG"]
            + ", passed staging and production smoke tests.",
}))
PY
                        curl -fsS -X POST \
                          -H "Authorization: Bearer ${GH_TOKEN}" \
                          -H "Accept: application/vnd.github+json" \
                          https://api.github.com/repos/${GITHUB_REPO}/releases \
                          -d @release.json > /dev/null
                        echo "GitHub release v${IMAGE_TAG} created"
                    '''
                }
            }
            post {
                always {
                    junit allowEmptyResults: true, testResults: 'smoke-prod.xml'
                }
            }
        }

        stage('Monitoring') {
            steps {
                withCredentials([
                    usernamePassword(credentialsId: 'gmail-smtp',
                                     usernameVariable: 'SMTP_USER',
                                     passwordVariable: 'SMTP_PASS'),
                    string(credentialsId: 'grafana-admin', variable: 'GRAFANA_ADMIN_PASSWORD')
                ]) {
                    sh '''
                        echo "== Preparing alerting config =="
                        sed -e "s|__SMTP_USER__|${SMTP_USER}|g" \
                            -e "s|__SMTP_PASS__|${SMTP_PASS}|g" \
                            deploy/monitoring/alertmanager/alertmanager.yml.template \
                            > deploy/monitoring/alertmanager/alertmanager.yml

                        echo "Validating Prometheus config and alert rules"
                        docker run --rm -v "$PWD/deploy/monitoring/prometheus:/etc/prometheus:ro" \
                          --entrypoint promtool prom/prometheus:latest \
                          check config /etc/prometheus/prometheus.yml
                        echo "Validating Alertmanager config"
                        docker run --rm -v "$PWD/deploy/monitoring/alertmanager:/etc/alertmanager:ro" \
                          --entrypoint amtool prom/alertmanager:latest \
                          check-config /etc/alertmanager/alertmanager.yml

                        echo "== Starting Prometheus, Alertmanager and Grafana =="
                        docker compose -f ${PROD_COMPOSE} up -d prometheus alertmanager grafana

                        for i in $(seq 1 20); do
                          curl -fs http://localhost:9090/-/ready > /dev/null && break
                          sleep 2
                        done
                        for i in $(seq 1 20); do
                          curl -fs http://localhost:9093/-/ready > /dev/null && break
                          sleep 2
                        done
                        curl -fs -X POST http://localhost:9090/-/reload || true
                        curl -fs -X POST http://localhost:9093/-/reload || true

                        echo "== Checking Prometheus can see production =="
                        up_ok=0
                        for i in $(seq 1 12); do
                          if curl -s -G --data-urlencode 'query=up{job="rivertrail"}' http://localhost:9090/api/v1/query \
                             | python3 -c 'import sys, json; r = json.load(sys.stdin)["data"]["result"]; sys.exit(0 if r and r[0]["value"][1] == "1" else 1)'; then
                            up_ok=1
                            break
                          fi
                          sleep 5
                        done
                        [ "$up_ok" = "1" ] || { echo "Prometheus cannot scrape the production app"; exit 1; }
                        echo "Prometheus target rivertrail is UP"

                        curl -s http://localhost:9090/api/v1/rules \
                          | python3 -c 'import sys, json; g = json.load(sys.stdin)["data"]["groups"]; names = [x["name"] for grp in g for x in grp["rules"]]; print("Alert rules loaded:", ", ".join(names)); sys.exit(0 if len(names) >= 3 else 1)'

                        curl -fs http://localhost:9093/-/ready > /dev/null && echo "Alertmanager is ready"
                        for i in $(seq 1 15); do
                          curl -fs http://localhost:3030/api/health > /dev/null && break
                          sleep 2
                        done
                        curl -fs http://localhost:3030/api/health > /dev/null && echo "Grafana is ready"

                        echo "Grafana: http://localhost:3030   Prometheus alerts: http://localhost:9090/alerts   Alertmanager: http://localhost:9093"
                    '''
                }
            }
        }
    }

    post {
        success {
            echo "Release ${IMAGE_TAG} is live at http://localhost:${PROD_PORT} and monitored in Grafana at http://localhost:3030"
        }
        failure {
            echo "Pipeline failed for ${IMAGE_NAME}:${IMAGE_TAG}. Check the stage logs above."
        }
    }
}
