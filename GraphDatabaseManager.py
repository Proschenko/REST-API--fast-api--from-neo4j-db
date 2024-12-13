import os
from neo4j import GraphDatabase, Transaction
from dotenv import load_dotenv

# Загрузка переменных из .env файла
load_dotenv()

class GraphDatabaseManager:
    def __init__(self, connection_uri, username, password):
        self.db_driver = GraphDatabase.driver(connection_uri, auth=(username, password))
        
        # Проверка подключения
        with self.db_driver.session() as session:
            result = session.run("RETURN 1")
            if result.single() is None:
                raise Exception("Не удалось подключиться к базе данных Neo4j")
            print("Успешное подключение к базе данных Neo4j")

    def close_connection(self):
        self.db_driver.close()

    def fetch_all_entities(self):
        query = "MATCH (e) RETURN e.id AS id, labels(e) AS label"
        with self.db_driver.session() as session:
            query_result = session.run(query)
            return [{"id": record["id"], "label": record["label"][0]} for record in query_result]

    def fetch_entity_with_associations(self, entity_id):
        query = """
        MATCH (e)-[r]-(t)
        WHERE e.id = $id
        RETURN e AS entity, r AS association, t AS target_entity
        """
        with self.db_driver.session() as session:
            query_result = session.run(query, id=entity_id)
            entities_data = []
            for record in query_result:
                entities_data.append({
                    "entity": {
                        "id": record["entity"].element_id,
                        "label": record["entity"].labels,
                        "properties": dict(record["entity"]),
                    },
                    "association": {
                        "type": record["association"].type,
                        "properties": dict(record["association"]),
                    },
                    "target_entity": {
                        "id": record["target_entity"].element_id,
                        "label": record["target_entity"].labels,
                        "properties": dict(record["target_entity"]),
                    }
                })
            return entities_data

    def fetch_all_entities_with_associations(self):
        query = """
        MATCH (e)-[r]-(t)
        RETURN e AS entity, r AS association, t AS target_entity
        """
        with self.db_driver.session() as session:
            query_result = session.run(query)

            entity_associations = {}

            for record in query_result:
                entity = record["entity"]
                entity_id = entity.element_id
                if entity_id not in entity_associations:
                    entity_associations[entity_id] = {
                        "entity": {
                            "id": entity.element_id,
                            "label": entity.labels,
                            "properties": dict(entity),
                        },
                        "associations": []
                    }

                entity_associations[entity_id]["associations"].append({
                    "association": {
                        "type": record["association"].type,
                        "properties": dict(record["association"]),
                    },
                    "target_entity": {
                        "id": record["target_entity"].element_id,
                        "label": record["target_entity"].labels,
                        "properties": dict(record["target_entity"]),
                    }
                })

            return list(entity_associations.values())

    def create_entity_and_associations(self, label, attributes, associations):
        with self.db_driver.session() as session:
            session.execute_write(self._create_entity_with_associations, label, attributes, associations)

    @staticmethod
    def _create_entity_with_associations(tx: Transaction, label, attributes, associations):
        # Создание нового объекта
        create_entity_query = f"CREATE (e:{label} $attributes) RETURN e"
        entity = tx.run(create_entity_query, attributes=attributes).single()["e"]
        entity_id = entity.element_id

        # Установка ассоциаций
        for association in associations:
            tx.run(""" 
            MATCH (e), (t)
            WHERE e.id = $entity_id AND t.id = $target_id
            CREATE (e)-[r:ASSOCIATION_TYPE]->(t)
            SET r = $association_attributes
            """, entity_id=entity_id, target_id=association['target_id'],
                   association_attributes=association['attributes'])

    def remove_entity(self, entity_id):
        with self.db_driver.session() as session:
            session.execute_write(self._remove_entity, entity_id)

    @staticmethod
    def _remove_entity(tx: Transaction, entity_id):
        # Удаление объекта и всех связанных с ним ассоциаций
        tx.run("MATCH (e) WHERE e.id = $id DETACH DELETE e", id=entity_id)


if __name__ == "__main__":
    # Параметры подключения из .env файла
    connection_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    username = os.getenv("NEO4J_USERNAME")
    password = os.getenv("NEO4J_PASSWORD")

    # Проверка, что переменные окружения загружены правильно
    if not username or not password:
        print("Ошибка: Не указаны переменные для подключения к базе данных Neo4j в .env файле.")
        exit(1)

    print(f"Подключение к базе данных Neo4j с URI: {connection_uri} и пользователем: {username}")

    # Инициализация работы с базой данных
    db_manager = GraphDatabaseManager(connection_uri, username, password)

    print("Получение всех объектов с ассоциациями:")
    all_entities = db_manager.fetch_all_entities_with_associations()
    for entity in all_entities[:100]:
        print(entity, end="\n\n")

    # Закрытие подключения к базе данных
    db_manager.close_connection()
