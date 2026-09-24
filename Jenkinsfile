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

                    echo "Waiting for the app to start..."
                    for i in $(seq 1 15); do
                      curl -fs http://localhost:${STAGING_PORT}/health && break
                      sleep 2
                    done

                    echo ""
                    echo "== Smoke tests against staging =="
                    curl -fs http://localhost:${STAGING_PORT}/health
                    echo ""
                    curl -fs -o /dev/null -w "Home page HTTP %{http_code}\n" http://localhost:${STAGING_PORT}/
                    curl -fs http://localhost:${STAGING_PORT}/api/reviews > /dev/null && echo "Reviews API OK"
                    curl -fs http://localhost:${STAGING_PORT}/metrics > /dev/null && echo "Metrics endpoint OK"
                '''
            }
        }
    }

    post {
        success {
            echo "Pipeline passed for ${IMAGE_NAME}:${IMAGE_TAG}. Staging is live at http://localhost:${STAGING_PORT}"
        }
        failure {
            echo "Pipeline failed for ${IMAGE_NAME}:${IMAGE_TAG}. Check the stage logs above."
        }
    }
}
