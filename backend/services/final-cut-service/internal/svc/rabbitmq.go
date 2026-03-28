package svc

import (
	"short-drama-platform/final-cut-service/internal/config"

	amqp "github.com/rabbitmq/amqp091-go"
)

type RabbitMQClient struct {
	conn    *amqp.Connection
	channel *amqp.Channel
	config  config.RabbitMQConfig
}

func NewRabbitMQClient(cfg config.RabbitMQConfig) RabbitMQClient {
	conn, err := amqp.Dial(cfg.Host + ":" + cfg.Port)
	if err != nil {
		panic(err)
	}

	channel, err := conn.Channel()
	if err != nil {
		conn.Close()
		panic(err)
	}

	return RabbitMQClient{
		conn:    conn,
		channel: channel,
		config:  cfg,
	}
}

func (r *RabbitMQClient) Publish(queueName string, body []byte) error {
	q, err := r.channel.QueueDeclare(
		queueName,
		true,
		false,
		false,
		false,
		nil,
	)
	if err != nil {
		return err
	}

	return r.channel.Publish(
		"",
		q.Name,
		false,
		false,
		amqp.Publishing{
			ContentType: "application/json",
			Body:        body,
		},
	)
}

func (r *RabbitMQClient) Consume(queueName string, consumerName string) (<-chan amqp.Delivery, error) {
	q, err := r.channel.QueueDeclare(
		queueName,
		true,
		false,
		false,
		false,
		nil,
	)
	if err != nil {
		return nil, err
	}

	return r.channel.Consume(
		q.Name,
		consumerName,
		true,
		false,
		false,
		false,
		nil,
	)
}

func (r *RabbitMQClient) Close() error {
	if r.channel != nil {
		r.channel.Close()
	}
	if r.conn != nil {
		r.conn.Close()
	}
	return nil
}
