import os
import sqlite3
from neo4j import GraphDatabase


SQLITE_DB = "social_network.db"
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")


def fetch_sqlite_data():
    conn = sqlite3.connect(SQLITE_DB)
    conn.row_factory = sqlite3.Row

    users = conn.execute("""
        SELECT id, username, name
        FROM users
        ORDER BY id
    """).fetchall()

    posts = conn.execute("""
        SELECT id, user_id, content, timestamp
        FROM posts
        ORDER BY id
    """).fetchall()

    followers = conn.execute("""
        SELECT follower_id, followee_id
        FROM followers
    """).fetchall()

    conn.close()
    return users, posts, followers


def run_query(driver, query, **params):
    return driver.execute_query(
        query,
        parameters_=params,
        database_=NEO4J_DATABASE,
    )


def main():
    users, posts, followers = fetch_sqlite_data()

    driver = GraphDatabase.driver(
        NEO4J_URI,
        auth=(NEO4J_USERNAME, NEO4J_PASSWORD)
    )
    driver.verify_connectivity()

    run_query(driver, """
        CREATE CONSTRAINT unique_user_id IF NOT EXISTS
        FOR (u:User) REQUIRE u.id IS UNIQUE
    """)
    run_query(driver, """
        CREATE CONSTRAINT unique_username IF NOT EXISTS
        FOR (u:User) REQUIRE u.username IS UNIQUE
    """)
    run_query(driver, """
        CREATE CONSTRAINT unique_post_id IF NOT EXISTS
        FOR (p:Post) REQUIRE p.id IS UNIQUE
    """)

    run_query(driver, "MATCH (n) DETACH DELETE n")

    run_query(driver, """
        UNWIND $users AS user
        CREATE (:User {
            id: user.id,
            username: user.username,
            name: user.name
        })
    """, users=[dict(row) for row in users])

    run_query(driver, """
        UNWIND $posts AS post
        MATCH (u:User {id: post.user_id})
        CREATE (p:Post {
            id: post.id,
            content: post.content,
            timestamp: datetime(post.timestamp)
        })
        CREATE (u)-[:POSTED]->(p)
    """, posts=[dict(row) for row in posts])

    run_query(driver, """
        UNWIND $followers AS rel
        MATCH (follower:User {id: rel.follower_id})
        MATCH (followee:User {id: rel.followee_id})
        CREATE (follower)-[:FOLLOWS]->(followee)
    """, followers=[dict(row) for row in followers])

    driver.close()
    print("Migration complete.")


if __name__ == "__main__":
    main()