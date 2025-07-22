def register_swagger_path(swagger):
    swagger.add_path(
        path="/authorization",
        method="post",
        summary="Авторизация пользователя",
        description="""
            Создает токен авторизации для нового пользователя.
            Принимает username, возвращает token и time_limit.

            Запрос необходимо подавать с телом JSON формата:
            {
                "username":"Name"
            }

        """,
        request_body={
            "required": True,
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "username": {
                                "type": "string",
                                "example": "Victor"
                            }
                        },
                        "required": ["username"]
                    }
                }
            }
        },
        responses={
            "200": {
                "description": "Токен успешно создан",
                "content": {
                    "application/json": {
                        "example": {
                            "username": "Victor",
                            "token": "4d3fcbcb9f4f45ae9d9f9b9...",
                            "time_limit": "600"
                        }
                    }
                }
            },
            "400": {
                "description": "Ошибка в теле запроса",
                "content": {
                    "application/json": {
                        "example": {"Ошибка": "Имя для пользователя не указано"}
                    }
                }
            }
        }
    )

    swagger.add_path(
        path="/task",
        method="post",
        summary="Отправка аудиофайлов в очередь обработки",
        description="""
        Принимает один или несколько аудиофайлов (multipart/form-data) и ставит задачи в очередь.
        Проверяет наличие времени у пользователя, обновляет лимит и сохраняет задачи в БД.
        """,
        request_body={
            "required": True,
            "content": {
                "multipart/form-data": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "audio": {
                                "type": "array",
                                "items": {
                                    "type": "string",
                                    "format": "binary"
                                },
                                "description": "Один или несколько аудиофайлов"
                            }
                        },
                        "required": ["audio"]
                    }
                }
            }
        },
        responses={
            "200": {
                "description": "Успешная постановка задачи в очередь",
                "content": {
                    "application/json": {
                        "example": [
                            {
                                "task_id": "abc123",
                                "file_name": "audio1.wav",
                                "remaining_time": 540
                            },
                            {
                                "task_id": "def456",
                                "file_name": "audio2.wav",
                                "remaining_time": 480
                            }
                        ]
                    }
                }
            },
            "400": {
                "description": "Ошибка валидации или недостаточно времени",
                "content": {
                    "application/json": {
                        "examples": {
                            "invalid_format": {
                                "summary": "Неподдерживаемый формат",
                                "value": {"Ошибка": "Неподдерживаемый формат аудио"}
                            },
                            "not_enough_time": {
                                "summary": "Недостаточно времени",
                                "value": {"Ошибка": "Недостаточно времени. Осталось: 10 сек, требуется: 25 сек."}
                            },
                            "no_audio": {
                                "summary": "Аудио не найдены",
                                "value": {"Ошибка": "Аудио не найдены"}
                            }
                        }
                    }
                }
            }
        },
        security=[{"BearerAuth": []}]
    )

    swagger.add_path(
        path="/status",
        method="get",
        summary="Получение статуса задач",
        description="""
        Возвращает статус задачи по task_id, либо список всех задач пользователя с пагинацией.<br>
        Требуется заголовок Authorization: Bearer &lt;token&gt;.<br>
        """,
        parameters=[
            {
                "name": "task_id",
                "in": "query",
                "required": False,
                "description": "ID конкретной задачи",
                "schema": {"type": "string", "example": "abc123"}
            },
            {
                "name": "status",
                "in": "query",
                "required": False,
                "description": "Фильтрация задач по статусу: queue, process, done, error",
                "schema": {"type": "string", "example": "done"}
            },
            {
                "name": "page",
                "in": "query",
                "required": False,
                "description": "Номер страницы (по умолчанию 1)",
                "schema": {"type": "integer", "example": 1}
            },
            {
                "name": "per_page",
                "in": "query",
                "required": False,
                "description": "Количество задач на страницу (по умолчанию 10)",
                "schema": {"type": "integer", "example": 10}
            }
        ],
        responses={
            "200": {
                "description": "Успешный ответ со статусами задач",
                "content": {
                    "application/json": {
                        "examples": {
                            "tasks": {
                                "summary": "Список задач",
                                "value": {
                                    "status": "done",
                                    "page": 1,
                                    "per_page": 10,
                                    "total_tasks": 2,
                                    "total_pages": 1,
                                    "tasks": [
                                        {"task_id": "abc123"},
                                        {"task_id": "def456"}
                                    ]
                                }
                            }
                        }
                    }
                }
            },
            "400": {
                "description": "Ошибка фильтрации по статусу",
                "content": {
                    "application/json": {
                        "example": {"error": "Некорректный статус. Допустимые значения: queue, process, done, error"}
                    }
                }
            }
        },
        security=[{"BearerAuth": []}]
    )

    swagger.add_path(
        path="/download",
        method="get",
        summary="Скачать результат обработки",
        description="""
        Позволяет скачать результат обработки задачи в формате txt или json.<br>
        Требуется заголовок Authorization: Bearer &lt;token&gt;.
        """,
        parameters=[
            {
                "name": "task_id",
                "in": "query",
                "required": True,
                "description": "ID задачи, результат которой необходимо скачать",
                "schema": {"type": "string", "example": "abc123"}
            },
            {
                "name": "type",
                "in": "query",
                "required": True,
                "description": "Тип файла: txt или json",
                "schema": {
                    "type": "string",
                    "enum": ["txt", "json"],
                    "example": "json"
                }
            }
        ],
        responses={
            "200": {"description": "Файл успешно найден"},
            "400": {
                "description": "Неверные параметры",
                "content": {
                    "application/json": {
                        "examples": {
                            "missing_parameters": {
                                "summary": "Отсутствуют параметры",
                                "value": {"Ошибка": "Необходимо указать task_id и тип файла (type=txt|json)"}
                            },
                            "invalid_type": {
                                "summary": "Неверный тип",
                                "value": {"Ошибка": "Недопустимый тип файла. Разрешены: txt, json"}
                            }
                        }
                    }
                }
            },
            "404": {
                "description": "Файл или задача не найдены",
                "content": {
                    "application/json": {
                        "examples": {
                            "not_found": {
                                "summary": "Задача или файл не найдены",
                                "value": {"Ошибка": "Задача не найдена или доступ запрещён"}
                            },
                            "file_missing": {
                                "summary": "Файл отсутствует",
                                "value": {"Ошибка": "Файл не найден"}
                            }
                        }
                    }
                }
            },
            "500": {
                "description": "Ошибка сервера",
                "content": {
                    "application/json": {
                        "example": {"Ошибка": "Непредвиденная ошибка: ..."}
                    }
                }
            }
        },
        security=[{"BearerAuth": []}]
    )
    